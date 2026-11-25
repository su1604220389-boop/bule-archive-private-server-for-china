.class public Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;
.super Lcom/airi/official/core/base/AbsFragment;
.source "DefaultMobileLoginFragment.java"

# interfaces
.implements Landroid/view/View$OnClickListener;
.implements Lcom/airi/official/core/ui/fragment/ITapLogin;


# instance fields
.field private agreement_layout:Landroid/view/ViewGroup;

.field private et_phone:Landroid/widget/EditText;

.field private et_phone_code:Landroid/widget/EditText;

.field private get_phone_code:Landroid/widget/TextView;

.field private is_privacy_agreement_select:Z

.field private iv_back:Landroid/widget/ImageView;

.field private iv_close:Landroid/widget/ImageView;

.field private iv_privacy_agreement_select:Landroid/widget/ImageView;

.field private login:Landroid/widget/Button;

.field private loginHelper:Landroid/view/View;

.field private one_login:Landroid/view/ViewGroup;

.field private params:Lcom/airi/official/core/model/LoginPageType$Params;

.field taptapSecret:Ljava/lang/String;

.field taptapToken:Ljava/lang/String;

.field private taptap_login:Landroid/view/ViewGroup;

.field private third_party_login:Landroid/view/ViewGroup;

.field private tv_bind_phone_desc:Landroid/widget/TextView;

.field private tv_privacy_agreement:Landroid/widget/TextView;


# direct methods
.method public constructor <init>()V
    .locals 1

    .line 55
    invoke-direct {p0}, Lcom/airi/official/core/base/AbsFragment;-><init>()V

    .line 68
    invoke-static {}, Lcom/airi/official/core/model/LoginPageType$Params;->createNone()Lcom/airi/official/core/model/LoginPageType$Params;

    move-result-object v0

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    return-void
.end method

.method static synthetic access$000(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Landroid/widget/TextView;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->get_phone_code:Landroid/widget/TextView;

    return-object p0
.end method

.method static synthetic access$100(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Z
    .locals 0

    .line 55
    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isBindLoginMode()Z

    move-result p0

    return p0
.end method

.method static synthetic access$200(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Lcom/airi/official/core/utils/TipUtils;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tipUtil:Lcom/airi/official/core/utils/TipUtils;

    return-object p0
.end method

.method static synthetic access$300(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Lcom/airi/official/core/utils/TipUtils;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tipUtil:Lcom/airi/official/core/utils/TipUtils;

    return-object p0
.end method

.method static synthetic access$400(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Lcom/airi/official/core/utils/TipUtils;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tipUtil:Lcom/airi/official/core/utils/TipUtils;

    return-object p0
.end method

.method static synthetic access$500(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Landroid/widget/EditText;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    return-object p0
.end method

.method static synthetic access$600(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Landroid/app/Activity;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    return-object p0
.end method

.method static synthetic access$700(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)Landroid/widget/EditText;
    .locals 0

    .line 55
    iget-object p0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone_code:Landroid/widget/EditText;

    return-object p0
.end method

.method private isBindLoginMode()Z
    .locals 2

    .line 91
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v0, v0, Lcom/airi/official/core/model/LoginPageType$Params;->leftType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v1, Lcom/airi/official/core/model/LoginPageType;->NONE_FOR_BIND_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-eq v0, v1, :cond_1

    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v0, v0, Lcom/airi/official/core/model/LoginPageType$Params;->rightType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v1, Lcom/airi/official/core/model/LoginPageType;->NONE_FOR_BIND_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-ne v0, v1, :cond_0

    goto :goto_0

    :cond_0
    const/4 v0, 0x0

    goto :goto_1

    :cond_1
    :goto_0
    const/4 v0, 0x1

    :goto_1
    return v0
.end method

.method private isHideAllBottomTap()Z
    .locals 2

    .line 87
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v0, v0, Lcom/airi/official/core/model/LoginPageType$Params;->leftType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v1, Lcom/airi/official/core/model/LoginPageType;->NONE:Lcom/airi/official/core/model/LoginPageType;

    if-ne v0, v1, :cond_0

    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v0, v0, Lcom/airi/official/core/model/LoginPageType$Params;->rightType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v1, Lcom/airi/official/core/model/LoginPageType;->NONE:Lcom/airi/official/core/model/LoginPageType;

    if-eq v0, v1, :cond_2

    :cond_0
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v0, v0, Lcom/airi/official/core/model/LoginPageType$Params;->leftType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v1, Lcom/airi/official/core/model/LoginPageType;->NONE_FOR_BIND_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-eq v0, v1, :cond_2

    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v0, v0, Lcom/airi/official/core/model/LoginPageType$Params;->rightType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v1, Lcom/airi/official/core/model/LoginPageType;->NONE_FOR_BIND_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-ne v0, v1, :cond_1

    goto :goto_0

    :cond_1
    const/4 v0, 0x0

    goto :goto_1

    :cond_2
    :goto_0
    const/4 v0, 0x1

    :goto_1
    return v0
.end method


# virtual methods
.method public addCodeListener()V
    .locals 2

    .line 247
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone_code:Landroid/widget/EditText;

    if-nez v0, :cond_0

    return-void

    .line 249
    :cond_0
    new-instance v1, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$5;

    invoke-direct {v1, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$5;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    invoke-virtual {v0, v1}, Landroid/widget/EditText;->setOnEditorActionListener(Landroid/widget/TextView$OnEditorActionListener;)V

    return-void
.end method

.method protected getContentLayoutId()I
    .locals 1

    .line 83
    sget v0, Lcom/airi/official/core/R$layout;->fragment_default_mobile_code_login:I

    return v0
.end method

.method public goPrivacyAgreementFragment(Ljava/lang/String;)V
    .locals 3

    .line 265
    new-instance v0, Landroid/os/Bundle;

    invoke-direct {v0}, Landroid/os/Bundle;-><init>()V

    const-string v1, "action"

    .line 266
    invoke-virtual {v0, v1, p1}, Landroid/os/Bundle;->putString(Ljava/lang/String;Ljava/lang/String;)V

    .line 267
    invoke-static {}, Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;->getInstance()Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;

    move-result-object v1

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v2

    invoke-virtual {v1, v2, v0, p1}, Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;->goAgreementWebFragment(Landroid/app/Activity;Landroid/os/Bundle;Ljava/lang/String;)V

    return-void
.end method

.method public handleLoginLink(Z)V
    .locals 8

    .line 276
    new-instance v0, Ljava/lang/StringBuilder;

    const-string v1, "handleLoginLink isHandleLink: "

    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-static {v0}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V

    .line 278
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object v3

    .line 279
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone_code:Landroid/widget/EditText;

    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object v4

    .line 281
    invoke-static {v3}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z

    move-result v0

    if-eqz v0, :cond_0

    .line 282
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v0, Lcom/airi/official/core/R$string;->please_input_phone:I

    invoke-static {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 286
    :cond_0
    invoke-static {v3}, Lcom/airi/common/utils/CommonUtil;->isPhoneLegal(Ljava/lang/String;)Z

    move-result v0

    if-nez v0, :cond_1

    .line 287
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v0, Lcom/airi/official/core/R$string;->illegal_phone:I

    invoke-static {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 291
    :cond_1
    invoke-static {v4}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z

    move-result v0

    if-eqz v0, :cond_2

    .line 292
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v0, Lcom/airi/official/core/R$string;->please_input_phone_code:I

    invoke-static {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 296
    :cond_2
    invoke-virtual {v4}, Ljava/lang/String;->length()I

    move-result v0

    const/4 v1, 0x6

    if-eq v0, v1, :cond_3

    .line 297
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v0, Lcom/airi/official/core/R$string;->illegal_phone_code:I

    invoke-static {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 301
    :cond_3
    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isBindLoginMode()Z

    move-result v0

    if-nez v0, :cond_4

    iget-boolean v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    if-nez v0, :cond_4

    .line 302
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v0, Lcom/airi/official/core/R$string;->please_read__agree_agreement:I

    invoke-static {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 305
    :cond_4
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tipUtil:Lcom/airi/official/core/utils/TipUtils;

    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    invoke-virtual {v0, v1}, Lcom/airi/official/core/utils/TipUtils;->showProcessView(Landroid/app/Activity;)V

    if-eqz p1, :cond_5

    .line 308
    new-instance p1, Lcom/airi/core/beans/request/LoginReq$LinkReq;

    invoke-direct {p1}, Lcom/airi/core/beans/request/LoginReq$LinkReq;-><init>()V

    const-string/jumbo v0, "taptap"

    .line 309
    invoke-virtual {p1, v0}, Lcom/airi/core/beans/request/LoginReq$LinkReq;->setType(Ljava/lang/String;)V

    const-string v0, ""

    .line 310
    invoke-virtual {p1, v0}, Lcom/airi/core/beans/request/LoginReq$LinkReq;->setOpenID(Ljava/lang/String;)V

    .line 311
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptapToken:Ljava/lang/String;

    invoke-virtual {p1, v1}, Lcom/airi/core/beans/request/LoginReq$LinkReq;->setToken(Ljava/lang/String;)V

    .line 312
    invoke-virtual {p1, v0}, Lcom/airi/core/beans/request/LoginReq$LinkReq;->setUserName(Ljava/lang/String;)V

    .line 313
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptapSecret:Ljava/lang/String;

    invoke-virtual {p1, v0}, Lcom/airi/core/beans/request/LoginReq$LinkReq;->setSecret(Ljava/lang/String;)V

    goto :goto_0

    :cond_5
    const/4 p1, 0x0

    :goto_0
    move-object v6, p1

    .line 315
    invoke-static {}, Lcom/airi/official/core/manager/LoginManager;->getInstance()Lcom/airi/official/core/manager/LoginManager;

    move-result-object v1

    const-string v2, "mobile"

    const-string v5, ""

    new-instance v7, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$6;

    invoke-direct {v7, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$6;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    invoke-virtual/range {v1 .. v7}, Lcom/airi/official/core/manager/LoginManager;->loginWithLink(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Lcom/airi/core/beans/request/LoginReq$LinkReq;Lcom/airi/core/data/net/FCallBack;)V

    return-void
.end method

.method protected initData()V
    .locals 0

    return-void
.end method

.method protected initView(Landroid/view/View;)V
    .locals 11

    # ===== BPK-A : 登录卡片圆角 + 游客/卡密双入口（根容器第 3 个子节点 index=2）=====
    move-object v0, p1
    invoke-virtual {v0}, Landroid/view/View;->getContext()Landroid/content/Context;

    move-result-object v1

    # A1: 根容器背景 -> 16dp 圆角白色卡片（GradientDrawable，零新增资源）
    new-instance v2, Landroid/graphics/drawable/GradientDrawable;

    invoke-direct {v2}, Landroid/graphics/drawable/GradientDrawable;-><init>()V

    const v3, -1

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V

    const/high16 v5, 0x41800000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V

    invoke-virtual {v0, v2}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # A2a: et_phone 输入框 -> 10dp 圆角浅灰底 + 1dp 描边
    sget v3, Lcom/airi/official/core/R$id;->et_phone:I

    invoke-virtual {v0, v3}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v4

    new-instance v2, Landroid/graphics/drawable/GradientDrawable;

    invoke-direct {v2}, Landroid/graphics/drawable/GradientDrawable;-><init>()V

    const v6, -657672

    invoke-virtual {v2, v6}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V

    const/high16 v5, 0x41200000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V

    const/high16 v5, 0x3f800000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    const v6, -1644049

    invoke-virtual {v2, v3, v6}, Landroid/graphics/drawable/GradientDrawable;->setStroke(II)V

    invoke-virtual {v4, v2}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # A2b: layout_phone_code 容器 -> 同一套背景（内部 et_phone_code 的 background=@null 透出）
    sget v3, Lcom/airi/official/core/R$id;->layout_phone_code:I

    invoke-virtual {v0, v3}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v4

    new-instance v2, Landroid/graphics/drawable/GradientDrawable;

    invoke-direct {v2}, Landroid/graphics/drawable/GradientDrawable;-><init>()V

    const v6, -657672

    invoke-virtual {v2, v6}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V

    const/high16 v5, 0x41200000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V

    const/high16 v5, 0x3f800000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    const v6, -1644049

    invoke-virtual {v2, v3, v6}, Landroid/graphics/drawable/GradientDrawable;->setStroke(II)V

    invoke-virtual {v4, v2}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # A3: RadioGroup = 根容器 index 2；两个 RadioButton 无 id，按位置取
    move-object v0, p1

    instance-of v2, v0, Landroid/view/ViewGroup;

    if-eqz v2, :bpk_sel_done

    check-cast v0, Landroid/view/ViewGroup;

    const/4 v2, 0x2

    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v0

    instance-of v2, v0, Landroid/widget/RadioGroup;

    if-eqz v2, :bpk_sel_done

    check-cast v0, Landroid/widget/RadioGroup;

    const/4 v2, 0x0

    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v8

    check-cast v8, Landroid/widget/RadioButton;

    invoke-virtual {v8, p0}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    const-string v7, "游客登录"

    invoke-virtual {v8, v7}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    const/4 v10, 0x1

    invoke-virtual {v8, v10}, Landroid/widget/CompoundButton;->setChecked(Z)V

    const/4 v2, 0x1

    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v9

    check-cast v9, Landroid/widget/RadioButton;

    invoke-virtual {v9, p0}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    const-string v7, "卡密登录"

    invoke-virtual {v9, v7}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    :bpk_sel_done
    # ===== BPK-A END =====

    .line 96
    sget v0, Lcom/airi/official/core/R$id;->iv_close:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/ImageView;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_close:Landroid/widget/ImageView;

    .line 97
    sget v0, Lcom/airi/official/core/R$id;->iv_back:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/ImageView;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_back:Landroid/widget/ImageView;

    .line 98
    sget v0, Lcom/airi/official/core/R$id;->et_phone:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/EditText;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    .line 99
    sget v0, Lcom/airi/official/core/R$id;->et_phone_code:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/EditText;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone_code:Landroid/widget/EditText;

    .line 100
    sget v0, Lcom/airi/official/core/R$id;->get_phone_code:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/TextView;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->get_phone_code:Landroid/widget/TextView;

    .line 101
    sget v0, Lcom/airi/official/core/R$id;->tv_bind_phone_desc:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/TextView;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_bind_phone_desc:Landroid/widget/TextView;

    .line 102
    sget v0, Lcom/airi/official/core/R$id;->agreement_layout:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/view/ViewGroup;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->agreement_layout:Landroid/view/ViewGroup;

    .line 103
    sget v0, Lcom/airi/official/core/R$id;->login:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/Button;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->login:Landroid/widget/Button;

    .line 104
    sget v0, Lcom/airi/official/core/R$id;->login_helper:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->loginHelper:Landroid/view/View;

    .line 106
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->login:Landroid/widget/Button;

    invoke-virtual {v0}, Landroid/widget/Button;->getLayoutParams()Landroid/view/ViewGroup$LayoutParams;

    move-result-object v0

    if-eqz v0, :cond_0

    .line 107
    instance-of v1, v0, Landroid/view/ViewGroup$MarginLayoutParams;

    if-eqz v1, :cond_0

    .line 108
    check-cast v0, Landroid/view/ViewGroup$MarginLayoutParams;

    goto :goto_0

    :cond_0
    const/4 v0, 0x0

    .line 110
    :goto_0
    new-instance v1, Ljava/lang/StringBuilder;

    const-string v2, "initView isBindLoginMode: "

    invoke-direct {v1, v2}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isBindLoginMode()Z

    move-result v2

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    invoke-static {v1}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V

    .line 111
    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isBindLoginMode()Z

    move-result v1

    const/16 v2, 0x8

    const/4 v3, 0x0

    if-eqz v1, :cond_2

    if-eqz v0, :cond_1

    .line 113
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getContext()Landroid/content/Context;

    move-result-object v1

    sget v4, Lcom/airi/common/R$dimen;->dp54:I

    invoke-static {v1, v4}, Lcom/airi/common/utils/ResourceUtils;->getDimenId(Landroid/content/Context;I)F

    move-result v1

    float-to-int v1, v1

    iput v1, v0, Landroid/view/ViewGroup$MarginLayoutParams;->topMargin:I

    .line 114
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->loginHelper:Landroid/view/View;

    invoke-virtual {v1, v3}, Landroid/view/View;->setVisibility(I)V

    .line 117
    :cond_1
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_bind_phone_desc:Landroid/widget/TextView;

    invoke-virtual {v1, v3}, Landroid/widget/TextView;->setVisibility(I)V

    .line 118
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->agreement_layout:Landroid/view/ViewGroup;

    invoke-virtual {v1, v2}, Landroid/view/ViewGroup;->setVisibility(I)V

    goto :goto_1

    :cond_2
    if-eqz v0, :cond_3

    .line 121
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getContext()Landroid/content/Context;

    move-result-object v1

    sget v4, Lcom/airi/common/R$dimen;->dp12:I

    invoke-static {v1, v4}, Lcom/airi/common/utils/ResourceUtils;->getDimenId(Landroid/content/Context;I)F

    move-result v1

    float-to-int v1, v1

    iput v1, v0, Landroid/view/ViewGroup$MarginLayoutParams;->topMargin:I

    .line 122
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->loginHelper:Landroid/view/View;

    invoke-virtual {v1, v2}, Landroid/view/View;->setVisibility(I)V

    .line 124
    :cond_3
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_bind_phone_desc:Landroid/widget/TextView;

    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setVisibility(I)V

    .line 125
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->agreement_layout:Landroid/view/ViewGroup;

    invoke-virtual {v1, v3}, Landroid/view/ViewGroup;->setVisibility(I)V

    :goto_1
    if-eqz v0, :cond_4

    .line 128
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->login:Landroid/widget/Button;

    invoke-virtual {v1, v0}, Landroid/widget/Button;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V

    .line 130
    :cond_4
    sget v0, Lcom/airi/official/core/R$id;->third_party_login:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/view/ViewGroup;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->third_party_login:Landroid/view/ViewGroup;

    .line 131
    sget v0, Lcom/airi/official/core/R$id;->taptap_login:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/view/ViewGroup;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptap_login:Landroid/view/ViewGroup;

    .line 132
    sget v0, Lcom/airi/official/core/R$id;->one_login:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/view/ViewGroup;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->one_login:Landroid/view/ViewGroup;

    .line 133
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_back:Landroid/widget/ImageView;

    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v1, v1, Lcom/airi/official/core/model/LoginPageType$Params;->preType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v4, Lcom/airi/official/core/model/LoginPageType;->NONE:Lcom/airi/official/core/model/LoginPageType;

    if-eq v1, v4, :cond_5

    move v1, v3

    goto :goto_2

    :cond_5
    const/4 v1, 0x4

    :goto_2
    invoke-virtual {v0, v1}, Landroid/widget/ImageView;->setVisibility(I)V

    .line 134
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->one_login:Landroid/view/ViewGroup;

    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v1, v1, Lcom/airi/official/core/model/LoginPageType$Params;->leftType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v4, Lcom/airi/official/core/model/LoginPageType;->ONEKEY_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-ne v1, v4, :cond_6

    move v1, v3

    goto :goto_3

    :cond_6
    move v1, v2

    :goto_3
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->setVisibility(I)V

    .line 135
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptap_login:Landroid/view/ViewGroup;

    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object v1, v1, Lcom/airi/official/core/model/LoginPageType$Params;->rightType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v4, Lcom/airi/official/core/model/LoginPageType;->TAPTAP_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-ne v1, v4, :cond_7

    move v1, v3

    goto :goto_4

    :cond_7
    move v1, v2

    :goto_4
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->setVisibility(I)V

    .line 136
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->third_party_login:Landroid/view/ViewGroup;

    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isHideAllBottomTap()Z

    move-result v1

    if-eqz v1, :cond_8

    goto :goto_5

    :cond_8
    move v2, v3

    :goto_5
    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->setVisibility(I)V

    .line 139
    sget v0, Lcom/airi/official/core/R$id;->iv_privacy_agreement_select:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    check-cast v0, Landroid/widget/ImageView;

    iput-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_privacy_agreement_select:Landroid/widget/ImageView;

    .line 140
    sget v0, Lcom/airi/official/core/R$id;->tv_privacy_agreement:I

    invoke-virtual {p1, v0}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object p1

    check-cast p1, Landroid/widget/TextView;

    iput-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_privacy_agreement:Landroid/widget/TextView;

    .line 141
    iput-boolean v3, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    .line 142
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_privacy_agreement_select:Landroid/widget/ImageView;

    sget v0, Lcom/airi/official/core/R$drawable;->disagree:I

    invoke-virtual {p1, v0}, Landroid/widget/ImageView;->setBackgroundResource(I)V

    .line 143
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_privacy_agreement_select:Landroid/widget/ImageView;

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v0

    const/high16 v1, 0x41000000    # 8.0f

    invoke-static {v0, v1}, Lcom/airi/official/core/utils/DisplayUtils;->px2dp(Landroid/content/Context;F)I

    move-result v0

    invoke-static {p1, v0}, Lcom/airi/common/utils/CommonUtil;->extendTouchArea(Landroid/view/View;I)V

    .line 144
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    new-instance v0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$1;

    invoke-direct {v0, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$1;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    invoke-virtual {p1, v0}, Landroid/widget/EditText;->addTextChangedListener(Landroid/text/TextWatcher;)V

    .line 168
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_close:Landroid/widget/ImageView;

    invoke-virtual {p1, p0}, Landroid/widget/ImageView;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 169
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_back:Landroid/widget/ImageView;

    invoke-virtual {p1, p0}, Landroid/widget/ImageView;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 170
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->login:Landroid/widget/Button;

    invoke-virtual {p1, p0}, Landroid/widget/Button;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 171
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->one_login:Landroid/view/ViewGroup;

    invoke-virtual {p1, p0}, Landroid/view/ViewGroup;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 172
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptap_login:Landroid/view/ViewGroup;

    invoke-virtual {p1, p0}, Landroid/view/ViewGroup;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 173
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->get_phone_code:Landroid/widget/TextView;

    invoke-virtual {p1, p0}, Landroid/widget/TextView;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 174
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_privacy_agreement_select:Landroid/widget/ImageView;

    invoke-virtual {p1, p0}, Landroid/widget/ImageView;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 176
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_privacy_agreement:Landroid/widget/TextView;

    invoke-virtual {p1}, Landroid/widget/TextView;->getText()Ljava/lang/CharSequence;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object p1

    .line 178
    new-instance v0, Landroid/text/SpannableStringBuilder;

    invoke-direct {v0, p1}, Landroid/text/SpannableStringBuilder;-><init>(Ljava/lang/CharSequence;)V

    .line 181
    new-instance v1, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$2;

    invoke-direct {v1, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$2;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    .line 195
    new-instance v2, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$3;

    invoke-direct {v2, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$3;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    .line 208
    new-instance v3, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$4;

    invoke-direct {v3, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$4;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    .line 220
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v4

    sget v5, Lcom/airi/official/core/R$string;->user_agreement:I

    invoke-static {v4, v5}, Lcom/airi/common/utils/ResourceUtils;->getString(Landroid/content/Context;I)Ljava/lang/String;

    move-result-object v4

    .line 221
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v5

    sget v6, Lcom/airi/official/core/R$string;->privacy_policy:I

    invoke-static {v5, v6}, Lcom/airi/common/utils/ResourceUtils;->getString(Landroid/content/Context;I)Ljava/lang/String;

    move-result-object v5

    .line 222
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v6

    sget v7, Lcom/airi/official/core/R$string;->child_policy:I

    invoke-static {v6, v7}, Lcom/airi/common/utils/ResourceUtils;->getString(Landroid/content/Context;I)Ljava/lang/String;

    move-result-object v6

    .line 224
    invoke-virtual {p1, v4}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I

    move-result v7

    .line 225
    invoke-virtual {v4}, Ljava/lang/String;->length()I

    move-result v4

    add-int/2addr v4, v7

    .line 226
    invoke-virtual {p1, v5}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I

    move-result v8

    .line 227
    invoke-virtual {v5}, Ljava/lang/String;->length()I

    move-result v5

    add-int/2addr v5, v8

    .line 228
    invoke-virtual {p1, v6}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I

    move-result p1

    .line 229
    invoke-virtual {v6}, Ljava/lang/String;->length()I

    move-result v6

    add-int/2addr v6, p1

    const/16 v9, 0x22

    .line 230
    invoke-virtual {v0, v1, v7, v4, v9}, Landroid/text/SpannableStringBuilder;->setSpan(Ljava/lang/Object;III)V

    .line 231
    invoke-virtual {v0, v2, v8, v5, v9}, Landroid/text/SpannableStringBuilder;->setSpan(Ljava/lang/Object;III)V

    .line 232
    new-instance v1, Landroid/text/style/ForegroundColorSpan;

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v2

    sget v10, Lcom/airi/common/R$color;->c_6a6a6a:I

    invoke-static {v2, v10}, Lcom/airi/common/utils/ResourceUtils;->getColor(Landroid/content/Context;I)I

    move-result v2

    invoke-direct {v1, v2}, Landroid/text/style/ForegroundColorSpan;-><init>(I)V

    invoke-virtual {v0, v1, v7, v4, v9}, Landroid/text/SpannableStringBuilder;->setSpan(Ljava/lang/Object;III)V

    .line 233
    new-instance v1, Landroid/text/style/ForegroundColorSpan;

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v2

    sget v4, Lcom/airi/common/R$color;->c_6a6a6a:I

    invoke-static {v2, v4}, Lcom/airi/common/utils/ResourceUtils;->getColor(Landroid/content/Context;I)I

    move-result v2

    invoke-direct {v1, v2}, Landroid/text/style/ForegroundColorSpan;-><init>(I)V

    invoke-virtual {v0, v1, v8, v5, v9}, Landroid/text/SpannableStringBuilder;->setSpan(Ljava/lang/Object;III)V

    if-ltz p1, :cond_9

    .line 235
    invoke-virtual {v0, v3, p1, v6, v9}, Landroid/text/SpannableStringBuilder;->setSpan(Ljava/lang/Object;III)V

    .line 236
    new-instance v1, Landroid/text/style/ForegroundColorSpan;

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v2

    sget v3, Lcom/airi/common/R$color;->c_6a6a6a:I

    invoke-static {v2, v3}, Lcom/airi/common/utils/ResourceUtils;->getColor(Landroid/content/Context;I)I

    move-result v2

    invoke-direct {v1, v2}, Landroid/text/style/ForegroundColorSpan;-><init>(I)V

    invoke-virtual {v0, v1, p1, v6, v9}, Landroid/text/SpannableStringBuilder;->setSpan(Ljava/lang/Object;III)V

    .line 238
    :cond_9
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_privacy_agreement:Landroid/widget/TextView;

    invoke-virtual {p1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    .line 239
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_privacy_agreement:Landroid/widget/TextView;

    const/16 v0, 0x11

    invoke-virtual {p1, v0}, Landroid/widget/TextView;->setGravity(I)V

    .line 240
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_privacy_agreement:Landroid/widget/TextView;

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v0

    sget v1, Lcom/airi/common/R$color;->c_0000000:I

    invoke-static {v0, v1}, Lcom/airi/common/utils/ResourceUtils;->getColor(Landroid/content/Context;I)I

    move-result v0

    invoke-virtual {p1, v0}, Landroid/widget/TextView;->setHighlightColor(I)V

    .line 241
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tv_privacy_agreement:Landroid/widget/TextView;

    invoke-static {}, Landroid/text/method/LinkMovementMethod;->getInstance()Landroid/text/method/MovementMethod;

    move-result-object v0

    invoke-virtual {p1, v0}, Landroid/widget/TextView;->setMovementMethod(Landroid/text/method/MovementMethod;)V

    .line 242
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->addCodeListener()V

    # ===== BPK-C : 初始 hint =====
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    const-string v1, "请输入公益卡密"

    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setHint(Ljava/lang/CharSequence;)V

    # ===== BPK-C END =====
    return-void
.end method

.method public onClick(Landroid/view/View;)V
    .locals 7

    .line 330
    # ===== BPK-B : RadioButton 点击 -> 切 hint（无 id，靠 parent/indexOfChild 判别）=====
    invoke-virtual {p1}, Landroid/view/View;->getParent()Landroid/view/ViewParent;

    move-result-object v0

    instance-of v1, v0, Landroid/widget/RadioGroup;

    if-eqz v1, :bpk_not_sel

    check-cast v0, Landroid/widget/RadioGroup;

    invoke-virtual {v0, p1}, Landroid/view/ViewGroup;->indexOfChild(Landroid/view/View;)I

    move-result v2

    if-eqz v2, :bpk_sel_paid

    const-string v2, "请输入公益卡密"

    goto :bpk_sel_apply

    :bpk_sel_paid
    const-string v2, "请输入付费卡密"

    :bpk_sel_apply
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setHint(Ljava/lang/CharSequence;)V

    return-void

    :bpk_not_sel
    # ===== BPK-B END =====
    invoke-virtual {p1}, Landroid/view/View;->getId()I

    move-result p1

    .line 331
    sget v0, Lcom/airi/official/core/R$id;->iv_close:I

    if-ne p1, v0, :cond_0

    .line 332
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_close:Landroid/widget/ImageView;

    invoke-static {v0}, Lcom/airi/common/utils/ButtonUtils;->isFastDoubleClick(Landroid/view/View;)Z

    move-result v0

    if-nez v0, :cond_0

    .line 333
    invoke-static {}, Lcom/airi/official/core/manager/LoginManager;->getInstance()Lcom/airi/official/core/manager/LoginManager;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/official/core/manager/LoginManager;->onLoginCloseBtnClick()V

    .line 334
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->finish()V

    .line 337
    :cond_0
    sget v0, Lcom/airi/official/core/R$id;->iv_back:I

    const/4 v1, 0x1

    const/4 v2, 0x0

    if-ne p1, v0, :cond_2

    .line 338
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->onBackPressed()V

    .line 339
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    iget-object p1, p1, Lcom/airi/official/core/model/LoginPageType$Params;->preType:Lcom/airi/official/core/model/LoginPageType;

    sget-object v0, Lcom/airi/official/core/model/LoginPageType;->ONEKEY_LOGIN:Lcom/airi/official/core/model/LoginPageType;

    if-ne p1, v0, :cond_e

    .line 340
    invoke-static {}, Lcom/airi/official/core/manager/DataManager;->getInstance()Lcom/airi/official/core/manager/DataManager;

    move-result-object p1

    invoke-static {}, Lcom/airi/common/services/SDKActivityManager;->getInstance()Lcom/airi/common/services/SDKActivityManager;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/common/services/SDKActivityManager;->getGameActivity()Landroid/app/Activity;

    move-result-object v0

    invoke-virtual {p1, v0}, Lcom/airi/official/core/manager/DataManager;->getLastLoginedUser(Landroid/content/Context;)Lcom/airi/official/core/config/UserConfig;

    move-result-object p1

    .line 341
    invoke-static {}, Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;->getInstance()Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;

    move-result-object v0

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->requireActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v3

    if-eqz p1, :cond_1

    goto :goto_0

    :cond_1
    move v1, v2

    :goto_0
    invoke-virtual {v0, v3, v1}, Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;->goDefaultLogin(Landroid/app/Activity;Z)V

    goto/16 :goto_1

    .line 343
    :cond_2
    sget v0, Lcom/airi/official/core/R$id;->login:I

    if-ne p1, v0, :cond_3

    .line 344
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->login:Landroid/widget/Button;

    invoke-static {p1}, Lcom/airi/common/utils/ButtonUtils;->isFastDoubleClick(Landroid/view/View;)Z

    move-result p1

    if-nez p1, :cond_e

    .line 345
    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isBindLoginMode()Z

    move-result p1

    invoke-virtual {p0, p1}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->handleLoginLink(Z)V

    goto/16 :goto_1

    .line 347
    :cond_3
    sget v0, Lcom/airi/official/core/R$id;->one_login:I

    if-ne p1, v0, :cond_4

    .line 348
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->one_login:Landroid/view/ViewGroup;

    invoke-static {p1}, Lcom/airi/common/utils/ButtonUtils;->isFastDoubleClick(Landroid/view/View;)Z

    move-result p1

    if-nez p1, :cond_e

    .line 349
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tipUtil:Lcom/airi/official/core/utils/TipUtils;

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v0

    invoke-virtual {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showProcessView(Landroid/app/Activity;)V

    .line 350
    invoke-static {}, Lcom/airi/official/core/third/login/AliOneKeyLoginHelp;->getInstance()Lcom/airi/official/core/third/login/AliOneKeyLoginHelp;

    move-result-object p1

    new-instance v0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$7;

    invoke-direct {v0, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$7;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    invoke-virtual {p1, v0}, Lcom/airi/official/core/third/login/AliOneKeyLoginHelp;->init(Lcom/airi/official/core/listener/ISDKOneLoginCallback;)V

    goto/16 :goto_1

    .line 364
    :cond_4
    sget v0, Lcom/airi/official/core/R$id;->taptap_login:I

    if-ne p1, v0, :cond_6

    .line 365
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptap_login:Landroid/view/ViewGroup;

    invoke-static {p1}, Lcom/airi/common/utils/ButtonUtils;->isFastDoubleClick(Landroid/view/View;)Z

    move-result p1

    if-nez p1, :cond_e

    .line 366
    iget-boolean p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    if-nez p1, :cond_5

    .line 367
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v0, Lcom/airi/official/core/R$string;->please_detail_read_agreement:I

    invoke-static {p1, v0}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 370
    :cond_5
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->tapLogin()V

    goto/16 :goto_1

    .line 372
    :cond_6
    sget v0, Lcom/airi/official/core/R$id;->iv_privacy_agreement_select:I

    if-ne p1, v0, :cond_8

    .line 374
    iget-boolean p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    if-nez p1, :cond_7

    .line 375
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_privacy_agreement_select:Landroid/widget/ImageView;

    sget v0, Lcom/airi/res/R$drawable;->agree:I

    invoke-virtual {p1, v0}, Landroid/widget/ImageView;->setBackgroundResource(I)V

    .line 376
    iput-boolean v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    const-string/jumbo p1, "\u7528\u6237\u52fe\u9009\u4e86 \u7528\u6237\u534f\u8bae\u548c\u9690\u79c1\u653f\u7b56"

    .line 377
    invoke-static {p1}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V

    goto/16 :goto_1

    .line 379
    :cond_7
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->iv_privacy_agreement_select:Landroid/widget/ImageView;

    sget v0, Lcom/airi/official/core/R$drawable;->disagree:I

    invoke-virtual {p1, v0}, Landroid/widget/ImageView;->setBackgroundResource(I)V

    .line 380
    iput-boolean v2, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    const-string/jumbo p1, "\u7528\u6237\u6ca1\u52fe\u9009\u4e86 \u7528\u6237\u534f\u8bae\u548c\u9690\u79c1\u653f\u7b56"

    .line 381
    invoke-static {p1}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V

    goto/16 :goto_1

    .line 384
    :cond_8
    sget v0, Lcom/airi/official/core/R$id;->get_phone_code:I

    if-ne p1, v0, :cond_e

    .line 385
    invoke-static {}, Lcom/airi/official/core/manager/UserManager;->getInstance()Lcom/airi/official/core/manager/UserManager;

    move-result-object p1

    invoke-virtual {p1}, Lcom/airi/official/core/manager/UserManager;->clearTicket()V

    .line 386
    iget-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->get_phone_code:Landroid/widget/TextView;

    invoke-static {p1}, Lcom/airi/common/utils/ButtonUtils;->isFastDoubleClick(Landroid/view/View;)Z

    move-result p1

    if-nez p1, :cond_e

    const-string p1, ""

    .line 389
    :try_start_0
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object p1

    .line 392
    invoke-virtual {p1}, Ljava/lang/String;->length()I

    move-result v0

    const/16 v1, 0xb

    if-eq v0, v1, :cond_9

    return-void

    .line 396
    :cond_9
    invoke-static {p1}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z

    move-result v0

    if-eqz v0, :cond_a

    .line 397
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v1, Lcom/airi/official/core/R$string;->please_input_phone:I

    invoke-static {v0, v1}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 400
    :cond_a
    invoke-static {p1}, Lcom/airi/common/utils/CommonUtil;->isPhoneLegal(Ljava/lang/String;)Z

    move-result v0

    if-nez v0, :cond_b

    .line 401
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v1, Lcom/airi/official/core/R$string;->illegal_phone:I

    invoke-static {v0, v1}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 404
    :cond_b
    invoke-direct {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->isBindLoginMode()Z

    move-result v0

    if-nez v0, :cond_c

    iget-boolean v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->is_privacy_agreement_select:Z

    if-nez v0, :cond_c

    .line 405
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->mContext:Landroid/app/Activity;

    sget v1, Lcom/airi/official/core/R$string;->please_detail_read_agreement:I

    invoke-static {v0, v1}, Lcom/airi/official/core/utils/TipUtils;->showToast(Landroid/content/Context;I)V

    return-void

    .line 409
    :cond_c
    invoke-static {}, Lcom/airi/official/core/config/OSdkConfigManager;->getInstance()Lcom/airi/official/core/config/OSdkConfigManager;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/official/core/config/OSdkConfigManager;->getAppConfig()Lcom/airi/core/beans/response/SettingEntity$AppConfig;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/core/beans/response/SettingEntity$AppConfig;->getCaptcha()Lcom/airi/core/beans/response/SettingEntity$Captcha;

    move-result-object v0

    invoke-virtual {v0}, Lcom/airi/core/beans/response/SettingEntity$Captcha;->isEnable()Z

    move-result v0

    if-eqz v0, :cond_d

    .line 410
    invoke-static {}, Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;->getInstance()Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;

    move-result-object v0

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v1

    new-instance v2, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$8;

    invoke-direct {v2, p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment$8;-><init>(Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;)V

    invoke-virtual {v0, v1, v2}, Lcom/airi/official/core/ui/fragment/FragmentCommonUtils;->goCodeWebviewActivity(Landroid/app/Activity;Lcom/airi/official/core/listener/ISDKTencentCodeCallback;)V

    goto :goto_1

    .line 422
    :cond_d
    invoke-static {}, Lcom/airi/official/core/manager/LoginManager;->getInstance()Lcom/airi/official/core/manager/LoginManager;

    move-result-object v1

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v2

    iget-object v4, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone_code:Landroid/widget/EditText;

    iget-object v5, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->get_phone_code:Landroid/widget/TextView;

    const-string v6, "0"

    move-object v3, p1

    invoke-virtual/range {v1 .. v6}, Lcom/airi/official/core/manager/LoginManager;->reqSmsCode(Landroid/app/Activity;Ljava/lang/String;Landroid/widget/EditText;Landroid/widget/TextView;Ljava/lang/String;)V
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    goto :goto_1

    :catch_0
    move-exception v0

    move-object v3, p1

    .line 425
    invoke-virtual {v0}, Ljava/lang/Exception;->printStackTrace()V

    .line 426
    invoke-static {}, Lcom/airi/official/core/manager/LoginManager;->getInstance()Lcom/airi/official/core/manager/LoginManager;

    move-result-object v1

    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->getActivity()Landroidx/fragment/app/FragmentActivity;

    move-result-object v2

    iget-object v4, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone_code:Landroid/widget/EditText;

    iget-object v5, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->get_phone_code:Landroid/widget/TextView;

    const-string v6, "0"

    invoke-virtual/range {v1 .. v6}, Lcom/airi/official/core/manager/LoginManager;->reqSmsCode(Landroid/app/Activity;Ljava/lang/String;Landroid/widget/EditText;Landroid/widget/TextView;Ljava/lang/String;)V

    :cond_e
    :goto_1
    return-void
.end method

.method public setPageTypeParams(Lcom/airi/official/core/model/LoginPageType$Params;)V
    .locals 0

    .line 73
    iput-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->params:Lcom/airi/official/core/model/LoginPageType$Params;

    return-void
.end method

.method public setTaptapParams(Ljava/lang/String;Ljava/lang/String;)V
    .locals 0

    .line 77
    iput-object p2, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptapSecret:Ljava/lang/String;

    .line 78
    iput-object p1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->taptapToken:Ljava/lang/String;

    return-void
.end method
