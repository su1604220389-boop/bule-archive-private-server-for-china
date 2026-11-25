#nullable enable

using System.Collections.Concurrent;
using System.Globalization;
using System.Reflection;
using Schale.MX.GameLogic.DBModel;
using Schale.MX.GameLogic.Parcel;
using Schale.MX.NetworkProtocol;

namespace BlueArchiveAPI.Services
{
    // >>> BAPATCH-EXPORTFILTER v1 BEGIN >>>
    // The server runs the JP excel table (/www/wwwroot/ba_srv/Resources/Dumped/ExcelDB.db, 311,083,008 B) and the
    // installed client runs the CN one (160,534,528 B, md5 824ce3a8bee2bb5ae36ada1ac95048f1). The server table is
    // a SUPERSET, so "the server has an Items row" does not mean "the client can parse that id".
    //
    // 2026-11-19 00:22: an Items row with UniqueId=90070000 (a 9e7 banner id that exists only in the server table)
    // was sent in Item_List. The client's ItemDBSchema has no such id, it could not parse /api/item/list, and login
    // looped with "同步账号信息时发生错误". Deleting the row fixed it - but deleting rows is not a fix: it loses
    // data, and the next client update would have been able to use that item.
    //
    // This class filters the EGRESS ONLY - the response object after the handler returns and before the gateway
    // serializes it. The row stays in the database; only what is sent changes. Every path that can put an ItemDB
    // into a response is covered by one hook (HandlerManager.Dispatch) instead of policing the ~145 places that
    // assign a ParcelResultDB, because a list of call sites is a list that goes stale.
    //
    // Allowlist: Resources/ClientItemIds.txt, generated from the client's own ItemDBSchema.Id by
    // work/ba/scripts/gen_client_item_ids.py (1803 ids). Override the file location with the
    // SHITTIM_CLIENT_ITEM_IDS environment variable (same pattern as SHITTIM_EXCELDB_SQLCIPHER_KEY).
    //
    // Failure policy is FAIL-OPEN, deliberately: a missing, empty or unreadable allowlist disables the filter and
    // logs one WARN. A broken list must never black out every item in the game; the login error it would cause is
    // exactly the class of outage this patch exists to prevent. The WARN is loud so it does not go unnoticed.
    //
    // Normal data is untouched: ids in the allowlist are never removed, never reordered and never rewritten, so a
    // response built from valid ids serializes to exactly the same bytes with the filter on or off.
    public static class ClientItemFilter
    {
        public const string ListFileName = "ClientItemIds.txt";
        public const string PathOverrideVariable = "SHITTIM_CLIENT_ITEM_IDS";

        // LoginSync ships its ItemListResponse one level down and some responses carry a ParcelResultDB inside a
        // child packet; four levels covers every shape in the protocol assembly with room to spare.
        private const int MaxDepth = 4;

        private static readonly object loadLock = new();
        private static HashSet<long>? allowedIds;   // null => filter disabled (fail-open)
        private static int loadState;               // 0 = not attempted, 1 = attempted (Volatile)
        private static readonly ConcurrentDictionary<long, byte> warnedIds = new();
        private static int walkFailedLogged;

        /// <summary>True once the allowlist loaded and the filter is removing ids.</summary>
        public static bool IsEnabled
        {
            get { EnsureLoaded(); return allowedIds != null; }
        }

        /// <summary>Number of ids in the loaded allowlist (0 when disabled).</summary>
        public static int AllowedCount
        {
            get { EnsureLoaded(); return allowedIds?.Count ?? 0; }
        }

        /// <summary>Loads the allowlist before the first request so a bad file shows up in the startup log.</summary>
        public static void Warmup() => EnsureLoaded();

        /// <summary>True when this item id may be sent to the client (always true while the filter is disabled).</summary>
        public static bool IsAllowed(long uniqueId)
        {
            EnsureLoaded();
            var allowed = allowedIds;
            return allowed == null || allowed.Contains(uniqueId);
        }

        /// <summary>Copy-style filter for callers that do not own the list; returns the same list when it is one.</summary>
        public static List<ItemDB> Filter(IEnumerable<ItemDB>? items)
        {
            EnsureLoaded();
            if (items is null) return [];
            if (items is List<ItemDB> list)
            {
                FilterInPlace(list);
                return list;
            }

            var allowed = allowedIds;
            var kept = new List<ItemDB>();
            foreach (var item in items)
            {
                if (item is null) continue;
                if (allowed == null || allowed.Contains(item.UniqueId)) kept.Add(item);
            }
            return kept;
        }

        /// <summary>Removes disallowed rows from the list in place, preserving the order of the survivors.</summary>
        public static bool FilterInPlace(List<ItemDB>? items, long accountServerId = 0, string where = "ItemDB list")
        {
            EnsureLoaded();
            var allowed = allowedIds;
            if (allowed == null || items == null || items.Count == 0) return false;

            return items.RemoveAll(item =>
            {
                if (item == null || allowed.Contains(item.UniqueId)) return false;
                WarnDropped(item.UniqueId, accountServerId, where);
                return true;
            }) > 0;
        }

        /// <summary>Removes disallowed rows from a ParcelResultDB-style dictionary in place.</summary>
        public static bool FilterInPlace(Dictionary<long, ItemDB>? items, long accountServerId = 0, string where = "ItemDB dictionary")
        {
            EnsureLoaded();
            var allowed = allowedIds;
            if (allowed == null || items == null || items.Count == 0) return false;

            List<long>? rejected = null;
            List<long>? rejectedUniqueIds = null;
            foreach (var pair in items)
            {
                if (pair.Value == null || allowed.Contains(pair.Value.UniqueId)) continue;
                (rejected ??= []).Add(pair.Key);
                (rejectedUniqueIds ??= []).Add(pair.Value.UniqueId);
            }
            if (rejected == null) return false;

            for (var i = 0; i < rejected.Count; i++)
            {
                items.Remove(rejected[i]);
                WarnDropped(rejectedUniqueIds![i], accountServerId, where);
            }
            return true;
        }

        /// <summary>
        /// The egress filter: walks one response object graph and drops every ItemDB whose UniqueId is not in the
        /// allowlist. Called once per response from HandlerManager.Dispatch, i.e. after the handler finished and
        /// before GatewayController serializes the packet.
        /// </summary>
        public static void FilterResponse(ResponsePacket? response, long accountServerId = 0)
        {
            EnsureLoaded();
            if (allowedIds == null || response == null) return;

            try
            {
                VisitResponse(response, accountServerId, 0);
            }
            catch (Exception ex)
            {
                // The filter must never take a request down. Log once, keep the response (partially filtered at worst).
                if (Interlocked.Exchange(ref walkFailedLogged, 1) == 0)
                    Warn($"export filter threw while scanning {response.GetType().Name} ({ex.GetBaseException().Message}); the response is returned unfiltered/partially filtered and this message is not repeated");
            }
        }

        private static void VisitResponse(ResponsePacket node, long accountServerId, int depth)
        {
            var plan = PlanFor(node.GetType());
            ApplyItemMembers(node, plan, accountServerId);

            if (depth >= MaxDepth) return;

            foreach (var property in plan.ParcelResults)
            {
                if (property.GetValue(node) is ParcelResultDB parcelResult)
                    ApplyItemMembers(parcelResult, PlanFor(parcelResult.GetType()), accountServerId);
            }

            foreach (var property in plan.Children)
            {
                if (property.GetValue(node) is ResponsePacket child && !ReferenceEquals(child, node))
                    VisitResponse(child, accountServerId, depth + 1);
            }
        }

        private static void ApplyItemMembers(object owner, Plan plan, long accountServerId)
        {
            foreach (var property in plan.ItemLists)
            {
                if (property.GetValue(owner) is List<ItemDB> items)
                    FilterInPlace(items, accountServerId, Where(owner, property));
            }

            foreach (var property in plan.ItemDictionaries)
            {
                if (property.GetValue(owner) is Dictionary<long, ItemDB> items)
                    FilterInPlace(items, accountServerId, Where(owner, property));
            }

            foreach (var property in plan.SingleItems)
            {
                if (property.GetValue(owner) is not ItemDB item || IsAllowedCore(item.UniqueId)) continue;
                WarnDropped(item.UniqueId, accountServerId, Where(owner, property));
                // A single-item field is only ever an echo of an item the client already has (Item_Lock,
                // Item_Consume, ...), so this should not fire; nulling it is still safer than sending an id the
                // client cannot resolve. The property is nullable in every response DTO that carries one.
                if (property.CanWrite) property.SetValue(owner, null);
            }
        }

        private static string Where(object owner, PropertyInfo property) => $"{owner.GetType().Name}.{property.Name}";

        private static bool IsAllowedCore(long uniqueId) => allowedIds == null || allowedIds.Contains(uniqueId);

        // ---- loading ---------------------------------------------------------------------------------------------

        private static void EnsureLoaded()
        {
            if (Volatile.Read(ref loadState) != 0) return;

            lock (loadLock)
            {
                if (loadState != 0) return;
                try
                {
                    LoadUncached();
                }
                catch (Exception ex)
                {
                    allowedIds = null;
                    Warn($"export filter disabled: could not read the client item allowlist ({ex.GetBaseException().Message}); every item id is forwarded unfiltered");
                }
                finally
                {
                    Volatile.Write(ref loadState, 1);
                }
            }
        }

        private static void LoadUncached()
        {
            var path = ResolveListPath();
            if (!File.Exists(path))
            {
                Warn($"export filter disabled: file missing ({path}); every item id is forwarded unfiltered");
                return;
            }

            var ids = new HashSet<long>();
            var rejected = 0;
            foreach (var line in File.ReadLines(path))
            {
                var trimmed = line.Trim();
                if (trimmed.Length == 0 || trimmed[0] == '#') continue;
                if (long.TryParse(trimmed, NumberStyles.Integer, CultureInfo.InvariantCulture, out var id))
                    ids.Add(id);
                else
                    rejected++;
            }

            if (ids.Count == 0)
            {
                Warn($"export filter disabled: file has no ids ({path}); every item id is forwarded unfiltered");
                return;
            }

            allowedIds = ids;
            Console.WriteLine($"[ClientItemFilter] loaded {ids.Count} client item id(s) from {path}; item export filter is ON"
                + (rejected > 0 ? $" ({rejected} line(s) were not ids and were ignored)" : ""));
        }

        private static string ResolveListPath()
        {
            var overridden = Environment.GetEnvironmentVariable(PathOverrideVariable);
            if (!string.IsNullOrWhiteSpace(overridden)) return overridden.Trim();

            // Same directory as ExcelTableService.ResourceDir: "Resources" next to the server binary. Kept as its own
            // expression rather than a call into ExcelTableService so this class stays dependency-free.
            var baseDir = Path.GetDirectoryName(AppContext.BaseDirectory) ?? AppContext.BaseDirectory;
            return Path.Combine(baseDir, "Resources", ListFileName);
        }

        private static void Warn(string message) => Console.WriteLine($"[ClientItemFilter] WARN: {message}");

        // One line per item id per process: a save that holds a bad id would otherwise log it on every login,
        // every Item_List and every reward claim.
        private static void WarnDropped(long uniqueId, long accountServerId, string where)
        {
            if (!warnedIds.TryAdd(uniqueId, 0)) return;
            Console.WriteLine($"[ClientItemFilter] WARN: withheld ItemDB UniqueId={uniqueId} (account {accountServerId}) from {where}: " +
                $"not in the CN client's ItemDBSchema ({ListFileName}); the row stays in the database and is only kept out of responses. " +
                "Further drops of this id are not logged this process.");
        }

        // ---- reflection plans ------------------------------------------------------------------------------------

        // Built once per response type, then reused: the walk must stay cheap enough to run on every packet.
        private sealed class Plan
        {
            public PropertyInfo[] ItemLists = [];
            public PropertyInfo[] ItemDictionaries = [];
            public PropertyInfo[] SingleItems = [];
            public PropertyInfo[] ParcelResults = [];
            public PropertyInfo[] Children = [];
        }

        private static readonly ConcurrentDictionary<Type, Plan> plans = new();

        private static Plan PlanFor(Type type) => plans.GetOrAdd(type, BuildPlan);

        private static Plan BuildPlan(Type type)
        {
            List<PropertyInfo> itemLists = [];
            List<PropertyInfo> itemDictionaries = [];
            List<PropertyInfo> singleItems = [];
            List<PropertyInfo> parcelResults = [];
            List<PropertyInfo> children = [];

            foreach (var property in type.GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                if (!property.CanRead || property.GetIndexParameters().Length != 0) continue;
                var propertyType = property.PropertyType;

                if (propertyType == typeof(List<ItemDB>)) itemLists.Add(property);
                else if (propertyType == typeof(Dictionary<long, ItemDB>)) itemDictionaries.Add(property);
                else if (propertyType == typeof(ItemDB)) singleItems.Add(property);
                else if (propertyType == typeof(ParcelResultDB)) parcelResults.Add(property);
                else if (typeof(ResponsePacket).IsAssignableFrom(propertyType)) children.Add(property);
            }

            return new Plan
            {
                ItemLists = [.. itemLists],
                ItemDictionaries = [.. itemDictionaries],
                SingleItems = [.. singleItems],
                ParcelResults = [.. parcelResults],
                Children = [.. children],
            };
        }
    }
    // <<< BAPATCH-EXPORTFILTER v1 END <<<
}
