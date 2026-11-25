/* =============================================================================
   ba_cardadmin / assets/app.js
   纯原生 JS，无任何依赖、无外网请求
   - 手机侧栏开关
   - 全选 / 已选计数
   - 行操作按钮（编辑/解绑/删除...）统一走 #rowact 表单
   - 复制（优先 navigator.clipboard，HTTP/IP 下退化为 textarea + execCommand）
   ========================================================================== */

(function () {
  'use strict';

  var CA = window.CA || {};

  /* ------------------------------------------------------------ 复制工具 --- */
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', 'readonly');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    ta.style.left = '-1000px';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    var ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  function copyText(text) {
    if (!text) {
      return Promise.reject(new Error('empty'));
    }
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        if (fallbackCopy(text)) {
          return true;
        }
        throw new Error('copy failed');
      });
    }
    return new Promise(function (resolve, reject) {
      if (fallbackCopy(text)) {
        resolve(true);
      } else {
        reject(new Error('copy failed'));
      }
    });
  }

  /* 轻量 toast */
  function toast(msg, isErr) {
    var el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = [
      'position:fixed', 'left:50%', 'bottom:26px', 'transform:translateX(-50%)',
      'background:' + (isErr ? '#cf222e' : '#101820'), 'color:#fff',
      'padding:8px 16px', 'border-radius:999px', 'font-size:13px', 'z-index:9999',
      'box-shadow:0 6px 24px rgba(0,0,0,.28)', 'opacity:0', 'transition:opacity .15s'
    ].join(';');
    document.body.appendChild(el);
    setTimeout(function () { el.style.opacity = '1'; }, 10);
    setTimeout(function () {
      el.style.opacity = '0';
      setTimeout(function () {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, 200);
    }, 1600);
  }

  CA.copyText = copyText;
  CA.toast = toast;

  /* -------------------------------------------------------- 行操作表单 --- */
  function submitRowAct(act, id) {
    var f = document.getElementById('rowact');
    var idEl = document.getElementById('ca-row-id');
    var opEl = document.getElementById('ca-row-op');
    if (!f || !idEl || !opEl) {
      return false;
    }
    idEl.value = id;
    opEl.value = act;
    f.submit();
    return true;
  }

  function bindRowAct() {
    document.addEventListener('click', function (ev) {
      var el = ev.target;
      while (el && el !== document.body && !(el.getAttribute && el.getAttribute('data-act'))) {
        el = el.parentNode;
      }
      if (!el || !el.getAttribute) {
        return;
      }
      var act = el.getAttribute('data-act');
      if (!act) {
        return;
      }
      ev.preventDefault();
      var id = el.getAttribute('data-id') || '';
      var cf = el.getAttribute('data-confirm');
      if (cf && !window.confirm(cf)) {
        return;
      }
      submitRowAct(act, id);
    });
  }

  /* ------------------------------------------------------------ 全选 --- */
  function bindSelectAll() {
    var all = document.getElementById('ca-check-all');
    var countEl = document.getElementById('ca-sel-count');
    var bulk = document.getElementById('bulkform');

    function boxes() {
      return Array.prototype.slice.call(document.querySelectorAll('.ca-pick'));
    }
    function refresh() {
      var n = boxes().filter(function (b) { return b.checked; }).length;
      if (countEl) {
        countEl.textContent = '已选 ' + n + ' 条';
      }
      if (all) {
        var total = boxes().length;
        all.checked = total > 0 && n === total;
        all.indeterminate = n > 0 && n < total;
      }
    }
    if (all) {
      all.addEventListener('change', function () {
        boxes().forEach(function (b) { b.checked = all.checked; });
        refresh();
      });
    }
    document.addEventListener('change', function (ev) {
      if (ev.target && ev.target.classList && ev.target.classList.contains('ca-pick')) {
        refresh();
      }
    });
    if (bulk) {
      bulk.addEventListener('submit', function () {});
    }
    refresh();
  }

  CA.confirmBulk = function (form) {
    var n = document.querySelectorAll('.ca-pick:checked').length;
    if (n === 0) {
      window.alert('请先勾选要操作的卡密');
      return false;
    }
    var opEl = form.querySelector('select[name="op"]');
    var op = opEl ? opEl.value : '';
    var label = {
      delete: '删除', disable: '禁用', enable: '启用', extend: '延期',
      never: '设为永不过期', unbind: '解绑设备'
    }[op] || op;
    var extra = '';
    if (op === 'extend') {
      var d = form.querySelector('input[name="days"]');
      extra = ' ' + (d ? d.value : '') + ' 天';
    }
    if (op === 'delete' || op === 'disable' || op === 'unbind') {
      if (!window.confirm('确认对选中的 ' + n + ' 条执行「' + label + extra + '」？\n删除不可恢复。')) {
        return false;
      }
    }
    return true;
  };

  /* ------------------------------------------------------------ 复制按钮 --- */
  function bindCopy() {
    document.addEventListener('click', function (ev) {
      var el = ev.target;
      while (el && el !== document.body && !(el.classList && el.classList.contains('btn-copy'))) {
        el = el.parentNode;
      }
      if (!el || !el.classList || !el.classList.contains('btn-copy')) {
        return;
      }
      ev.preventDefault();
      var direct = el.getAttribute('data-copy');
      var fetchUrl = el.getAttribute('data-fetch');

      function done() {
        var old = el.textContent;
        el.textContent = '已复制';
        setTimeout(function () { el.textContent = old; }, 1200);
      }

      if (direct) {
        copyText(direct).then(done).catch(function () { toast('复制失败，请手动选中', true); });
        return;
      }
      if (!fetchUrl) {
        return;
      }
      var fid = el.getAttribute('data-id');
      var ftoken = el.getAttribute('data-csrf') || '';
      if (!fid) {
        return;
      }
      el.textContent = '…';
      fetch(fetchUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Requested-With': 'fetch'
        },
        body: 'ajax=key&_csrf=' + encodeURIComponent(ftoken) + '&id=' + encodeURIComponent(fid)
      })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j || !j.ok) {
            throw new Error('no key');
          }
          return copyText(j.key);
        })
        .then(done)
        .catch(function () {
          el.textContent = '复制';
          toast('取明文失败，请点「显示明文」后复制', true);
        });
    });
  }

  /* -------------------------------------------------------- 一键复制全部 --- */
  function bindCopyAll() {
    var btn = document.getElementById('ca-copy-all');
    var ta = document.getElementById('ca-batch-text');
    if (!btn || !ta) {
      return;
    }
    btn.addEventListener('click', function () {
      copyText(ta.value).then(function () {
        var old = btn.textContent;
        btn.textContent = '已复制 ✓';
        setTimeout(function () { btn.textContent = old; }, 1400);
      }).catch(function () { toast('复制失败，请手动全选复制', true); });
    });
  }

  /* --------------------------------------------------------- data-toggle --- */
  function bindToggles() {
    document.addEventListener('click', function (ev) {
      var el = ev.target;
      while (el && el !== document.body && !(el.getAttribute && el.getAttribute('data-toggle'))) {
        el = el.parentNode;
      }
      if (!el || !el.getAttribute) {
        return;
      }
      var id = el.getAttribute('data-toggle');
      var t = id ? document.getElementById(id) : null;
      if (!t) {
        return;
      }
      ev.preventDefault();
      t.style.display = (t.style.display === 'none' || !t.style.display) ? '' : 'none';
    });
  }

  /* ------------------------------------------------------------- 侧栏 --- */
  function bindSidebar() {
    var burger = document.getElementById('ca-burger');
    if (burger) {
      burger.addEventListener('click', function (ev) {
        ev.preventDefault();
        document.body.classList.toggle('sidebar-open');
      });
    }
    document.addEventListener('click', function (ev) {
      if (!document.body.classList.contains('sidebar-open')) {
        return;
      }
      var t = ev.target;
      if (t && t.closest && t.closest('.sidebar')) {
        return;
      }
      if (t === burger) {
        return;
      }
      document.body.classList.remove('sidebar-open');
    });
  }

  /* ------------------------------------------------------ 永不过期联动 --- */
  function bindNeverCheckbox() {
    var cb = document.getElementById('exp_never');
    var input = document.getElementById('exp_at');
    if (!cb || !input) {
      return;
    }
    function sync() {
      input.disabled = cb.checked;
      if (cb.checked) {
        input.value = '';
      }
    }
    cb.addEventListener('change', sync);
    sync();
  }

  function boot() {
    bindRowAct();
    bindSelectAll();
    bindCopy();
    bindCopyAll();
    bindToggles();
    bindSidebar();
    bindNeverCheckbox();
  }

  window.CA = CA;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
