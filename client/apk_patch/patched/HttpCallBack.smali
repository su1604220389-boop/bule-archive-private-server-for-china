.class public abstract Lcom/airi/official/core/http/net/HttpCallBack;
.super Lcom/airi/core/data/net/AbstractCallBack;
.source "HttpCallBack.java"


# annotations
.annotation system Ldalvik/annotation/Signature;
    value = {
        "<T:",
        "Ljava/lang/Object;",
        ">",
        "Lcom/airi/core/data/net/AbstractCallBack<",
        "TT;>;"
    }
.end annotation


# direct methods
.method public constructor <init>()V
    .locals 0

    .line 25
    invoke-direct {p0}, Lcom/airi/core/data/net/AbstractCallBack;-><init>()V

    return-void
.end method

.method private handleErrorCode(ILjava/lang/String;)V
    .locals 4

    .line 70
    invoke-virtual {p0, p1}, Lcom/airi/official/core/http/net/HttpCallBack;->isHandleErrorCode(I)Z

    move-result v0

    .line 71
    invoke-static {p1}, Lcom/airi/official/core/http/net/ErrorCodeHandler;->getCodeInfoByCode(I)Lcom/airi/official/core/http/net/ErrorCodeInfo;

    move-result-object v1

    # ===== BPK-D : 用服务端 msg 重建 ErrorCodeInfo（保留 isLogout/isRemoveUserData）=====
    invoke-static {p2}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z

    move-result v2

    if-eqz v2, :bpk_keep_local

    invoke-virtual {v1}, Lcom/airi/official/core/http/net/ErrorCodeInfo;->component3()Z

    move-result v2

    invoke-virtual {v1}, Lcom/airi/official/core/http/net/ErrorCodeInfo;->component4()Z

    move-result v3

    new-instance v1, Lcom/airi/official/core/http/net/ErrorCodeInfo;

    invoke-direct {v1, p1, p2, v2, v3}, Lcom/airi/official/core/http/net/ErrorCodeInfo;-><init>(ILjava/lang/String;ZZ)V

    :bpk_keep_local
    # ===== BPK-D END =====

    .line 72
    new-instance v2, Ljava/lang/StringBuilder;

    const-string v3, "handleErrorCode_code: "

    invoke-direct {v2, v3}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v2, p1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object p1

    const-string v2, ", message: "

    invoke-virtual {p1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1, p2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    const-string p2, ", isHandleErrorCode: "

    invoke-virtual {p1, p2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1, v0}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    invoke-static {p1}, Lcom/airi/common/log/MyLog;->i(Ljava/lang/String;)V

    if-eqz v0, :cond_1

    .line 74
    invoke-static {}, Lcom/airi/official/core/manager/DataManager;->getInstance()Lcom/airi/official/core/manager/DataManager;

    move-result-object p1

    invoke-virtual {p1}, Lcom/airi/official/core/manager/DataManager;->getCurrLoginedUser()Lcom/airi/official/core/config/UserConfig;

    move-result-object p1

    if-nez p1, :cond_0

    .line 75
    invoke-virtual {p0}, Lcom/airi/official/core/http/net/HttpCallBack;->getRequestUid()J

    move-result-wide p1

    goto :goto_0

    :cond_0
    invoke-virtual {p1}, Lcom/airi/official/core/config/UserConfig;->getUid()J

    move-result-wide p1

    .line 76
    :goto_0
    invoke-static {}, Lcom/airi/common/services/SDKActivityManager;->getInstance()Lcom/airi/common/services/SDKActivityManager;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/common/services/SDKActivityManager;->getGameActivity()Landroid/app/Activity;

    move-result-object v0

    new-instance v2, Lcom/airi/official/core/http/net/HttpCallBack$$ExternalSyntheticLambda0;

    invoke-direct {v2, p0, v1}, Lcom/airi/official/core/http/net/HttpCallBack$$ExternalSyntheticLambda0;-><init>(Lcom/airi/official/core/http/net/HttpCallBack;Lcom/airi/official/core/http/net/ErrorCodeInfo;)V

    invoke-static {v0, p1, p2, v1, v2}, Lcom/airi/official/core/http/net/ErrorCodeHandler;->showUiByErrorCodeInfo(Landroid/app/Activity;JLcom/airi/official/core/http/net/ErrorCodeInfo;Lcom/airi/official/core/http/net/ErrorCodeHandleCallback;)V

    goto :goto_1

    .line 80
    :cond_1
    invoke-virtual {p0, v1}, Lcom/airi/official/core/http/net/HttpCallBack;->onError(Lcom/airi/official/core/http/net/ErrorCodeInfo;)V

    :goto_1
    return-void
.end method

.method private hideLoadingUi()V
    .locals 3

    .line 86
    :try_start_0
    invoke-static {}, Lcom/airi/common/services/SDKActivityManager;->getInstance()Lcom/airi/common/services/SDKActivityManager;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/common/services/SDKActivityManager;->getGameActivity()Landroid/app/Activity;

    move-result-object v0

    .line 87
    invoke-static {}, Lcom/airi/official/core/third/login/AliOneKeyLoginHelp;->getInstance()Lcom/airi/official/core/third/login/AliOneKeyLoginHelp;

    move-result-object v1

    invoke-virtual {v1}, Lcom/airi/official/core/third/login/AliOneKeyLoginHelp;->hideLoginLoading()V

    .line 88
    invoke-static {}, Lcom/airi/official/core/utils/TipUtils;->getInstance()Lcom/airi/official/core/utils/TipUtils;

    move-result-object v1

    invoke-virtual {v1, v0}, Lcom/airi/official/core/utils/TipUtils;->dismissProcessView(Landroid/app/Activity;)V
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    goto :goto_0

    :catch_0
    move-exception v0

    .line 90
    new-instance v1, Ljava/lang/StringBuilder;

    const-string v2, "hideLoadingUi_error msg: "

    invoke-direct {v1, v2}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v0}, Ljava/lang/Exception;->getMessage()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-static {v0}, Lcom/airi/common/log/MyLog;->e(Ljava/lang/String;)V

    :goto_0
    return-void
.end method


# virtual methods
.method public getRequestUid()J
    .locals 2

    const-wide/16 v0, 0x0

    return-wide v0
.end method

.method public isHandleErrorCode(I)Z
    .locals 0

    const/4 p1, 0x1

    return p1
.end method

.method synthetic lambda$handleErrorCode$0$com-airi-official-core-http-net-HttpCallBack(Lcom/airi/official/core/http/net/ErrorCodeInfo;Lcom/airi/official/core/http/net/ErrorCodeInfo;)V
    .locals 0

    .line 77
    invoke-virtual {p0, p1}, Lcom/airi/official/core/http/net/HttpCallBack;->onError(Lcom/airi/official/core/http/net/ErrorCodeInfo;)V

    return-void
.end method

.method public abstract onError(Lcom/airi/official/core/http/net/ErrorCodeInfo;)V
.end method

.method public onFailure(Lretrofit2/Call;Ljava/lang/Throwable;)V
    .locals 1
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Lretrofit2/Call<",
            "TT;>;",
            "Ljava/lang/Throwable;",
            ")V"
        }
    .end annotation

    .line 62
    invoke-direct {p0}, Lcom/airi/official/core/http/net/HttpCallBack;->hideLoadingUi()V

    .line 63
    new-instance p1, Ljava/lang/StringBuilder;

    const-string v0, "onFailure_http_error msg: "

    invoke-direct {p1, v0}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {p2}, Ljava/lang/Throwable;->getMessage()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {p1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    invoke-static {p1}, Lcom/airi/common/log/MyLog;->e(Ljava/lang/String;)V

    .line 65
    invoke-static {}, Lcom/airi/official/core/manager/TraceManager;->getInstance()Lcom/airi/official/core/manager/TraceManager;

    move-result-object p1

    invoke-virtual {p2}, Ljava/lang/Throwable;->getMessage()Ljava/lang/String;

    move-result-object p2

    invoke-virtual {p1, p2}, Lcom/airi/official/core/manager/TraceManager;->eventErr(Ljava/lang/String;)V

    .line 66
    invoke-static {}, Lcom/airi/common/services/SDKActivityManager;->getInstance()Lcom/airi/common/services/SDKActivityManager;

    move-result-object p1

    invoke-virtual {p1}, Lcom/airi/common/services/SDKActivityManager;->getApplicationContext()Landroid/content/Context;

    move-result-object p1

    sget p2, Lcom/airi/official/core/R$string;->net_error:I

    invoke-static {p1, p2}, Lcom/airi/common/utils/ResourceUtils;->getString(Landroid/content/Context;I)Ljava/lang/String;

    move-result-object p1

    const p2, 0x18c1c

    invoke-direct {p0, p2, p1}, Lcom/airi/official/core/http/net/HttpCallBack;->handleErrorCode(ILjava/lang/String;)V

    return-void
.end method

.method public abstract onResponse(Lcom/airi/core/beans/BaseResposeEntity;)V
.end method

.method public onResponse(Lretrofit2/Call;Lretrofit2/Response;)V
    .locals 8
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Lretrofit2/Call<",
            "TT;>;",
            "Lretrofit2/Response<",
            "TT;>;)V"
        }
    .end annotation

    const-string p1, "   busnessCode: "

    const-string v0, "HttpCallBack_onResponse "

    const-string v1, "onResponse_http_success httpCode: "

    const-string v2, "onResponse_http_error httpCode: "

    .line 30
    invoke-direct {p0}, Lcom/airi/official/core/http/net/HttpCallBack;->hideLoadingUi()V

    const/4 v3, -0x1

    const v4, 0x18c1c

    .line 34
    :try_start_0
    invoke-virtual {p2}, Lretrofit2/Response;->code()I

    move-result v5
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_1

    const/16 v6, 0xc8

    if-eq v5, v6, :cond_0

    .line 36
    :try_start_1
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0, v2}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v0, v5}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v0

    const-string v1, ",msg: "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {p2}, Lretrofit2/Response;->message()Ljava/lang/String;

    move-result-object p2

    invoke-virtual {v0, p2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p2

    invoke-virtual {p2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p2

    invoke-static {p2}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V

    const-string/jumbo p2, "unknown error"

    .line 37
    invoke-direct {p0, v4, p2}, Lcom/airi/official/core/http/net/HttpCallBack;->handleErrorCode(ILjava/lang/String;)V

    return-void

    .line 40
    :cond_0
    invoke-virtual {p2}, Lretrofit2/Response;->body()Ljava/lang/Object;

    move-result-object p2

    check-cast p2, Lcom/airi/core/beans/BaseResposeEntity;

    .line 41
    iget v4, p2, Lcom/airi/core/beans/BaseResposeEntity;->Code:I

    .line 47
    new-instance v7, Ljava/lang/StringBuilder;

    invoke-direct {v7, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v7, v5}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    invoke-static {v1}, Lcom/airi/common/log/MyLog;->i(Ljava/lang/String;)V

    if-eq v4, v6, :cond_1

    .line 49
    iget-object p2, p2, Lcom/airi/core/beans/BaseResposeEntity;->Msg:Ljava/lang/String;

    invoke-direct {p0, v4, p2}, Lcom/airi/official/core/http/net/HttpCallBack;->handleErrorCode(ILjava/lang/String;)V

    return-void

    .line 52
    :cond_1
    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1, v0}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-static {p2}, Lcom/airi/common/utils/GsonUtils;->gsonToString(Ljava/lang/Object;)Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-static {v0}, Lcom/airi/common/log/MyLog;->i(Ljava/lang/String;)V

    .line 53
    invoke-virtual {p0, p2}, Lcom/airi/official/core/http/net/HttpCallBack;->onResponse(Lcom/airi/core/beans/BaseResposeEntity;)V
    :try_end_1
    .catch Ljava/lang/Exception; {:try_start_1 .. :try_end_1} :catch_0

    goto :goto_1

    :catch_0
    move-exception p2

    goto :goto_0

    :catch_1
    move-exception p2

    move v5, v3

    .line 55
    :goto_0
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0, v2}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v0, v5}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1, v4}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object p1

    const-string v0, ",e:"

    invoke-virtual {p1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p2}, Ljava/lang/Exception;->getMessage()Ljava/lang/String;

    move-result-object p2

    invoke-virtual {p1, p2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    invoke-static {p1}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V

    .line 56
    invoke-static {}, Lcom/airi/common/services/SDKActivityManager;->getInstance()Lcom/airi/common/services/SDKActivityManager;

    move-result-object p1

    invoke-virtual {p1}, Lcom/airi/common/services/SDKActivityManager;->getApplicationContext()Landroid/content/Context;

    move-result-object p1

    sget p2, Lcom/airi/official/core/R$string;->UN_KNOW_ERROR:I

    invoke-static {p1, p2}, Lcom/airi/common/utils/ResourceUtils;->getString(Landroid/content/Context;I)Ljava/lang/String;

    move-result-object p1

    invoke-direct {p0, v3, p1}, Lcom/airi/official/core/http/net/HttpCallBack;->handleErrorCode(ILjava/lang/String;)V

    :goto_1
    return-void
.end method
