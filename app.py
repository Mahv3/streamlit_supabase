# streamlit_app.py

import os
from dotenv import load_dotenv
import streamlit as st
from supabase import create_client, Client
import urllib.parse
import time
from streamlit_extras.switch_page_button import switch_page

# --- 🔰 ページの最初に置く ― 最優先でリダイレクト判定 ----------
if st.session_state.get("redirect_to_dashboard"):
    st.session_state.redirect_to_dashboard = False  # ループ防止
    switch_page("dashboard")  # ファイル名ではなくページ名
# ----------------------------------------------------------------

# 1) 環境変数ロード
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8501") # Streamlitのサイトデフォルトはローカルホスト

# 2) Supabase クライアント生成
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 5) users テーブルにレコードがなければ作成
def ensure_user_record(sb: Client, user):
    # 存在チェック
    existing = sb.table("users").select("id").eq("id", user.id).execute()
    if existing.data == []:
        sb.table("users").insert({
            "id":      user.id,
            "email":   user.email,
        }).execute()

# Google認証のリダイレクトURIを生成
def get_google_oauth_url():
    # リダイレクト先はStreamlitアプリのURL（デプロイ時に変更が必要）
    redirect_uri = urllib.parse.quote(f"{SITE_URL}")
    provider = "google"
    # 明示的にアクセストークンをURLに含めるように指定
    return f"{SUPABASE_URL}/auth/v1/authorize?provider={provider}&redirect_to={redirect_uri}"

# URLからアクセストークンを取得
def process_google_callback():
    # JavaScriptで#access_tokenを?access_tokenに変換
    st.markdown("""
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            const hash = window.location.hash;
            if (hash && hash.includes("access_token")) {
                const query = new URLSearchParams(hash.substring(1));
                const token = query.get("access_token");
                if (token) {
                    const newUrl = `${window.location.pathname}?access_token=${token}`;
                    window.location.replace(newUrl);
                }
            }
        });
    </script>
    """, unsafe_allow_html=True)

    # クエリパラメータからトークンを取得
    if "access_token" not in st.query_params:
        return False  # JavaScriptでの変換を待つ

    access_token = st.query_params["access_token"]
    try:
        # ユーザー情報を取得
        res = sb.auth.get_user(access_token)
        if res.user:
            # セッションにユーザー情報を保存
            st.session_state.user = res.user
            st.session_state.token = access_token
            st.session_state.auth_method = "google"
            
            # ユーザーレコードを作成
            try:
                ensure_user_record(sb, res.user)
            except Exception as db_err:
                st.sidebar.warning(f"プロファイル作成エラー: {str(db_err)}")
            
            # リダイレクトフラグを立てて再読み込み
            st.session_state.redirect_to_dashboard = True
            st.experimental_set_query_params()  # URLからtokenを消す
            st.rerun()
            return True
    except Exception as e:
        st.error(f"認証エラー: {str(e)}")
    
    return False

# 認証コールバックの処理
process_google_callback()

# 3) 認証判定＆ログインフォーム
if "user" not in st.session_state:
    st.title("ログイン or 新規登録")
    
    # Google認証ボタンを追加
    st.markdown("### Googleでログイン")
    google_auth_url = get_google_oauth_url()
    st.markdown(f'<a href="{google_auth_url}" target="_self"><button style="background-color: #4285F4; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%;">Googleでログイン</button></a>', unsafe_allow_html=True)
    
    st.markdown("### または、メールアドレスでログイン")
    email = st.text_input("Email")
    pw    = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("ログイン"):
            res = sb.auth.sign_in_with_password({"email": email, "password": pw})
            if res.user:
                st.session_state.user = res.user
                st.session_state.auth_method = "email"  # 認証方法を記録
                st.rerun()
            else:
                st.error("認証に失敗しました")

    with col2:
        if st.button("新規登録"):
            try:
                # email_confirmをfalseに設定してメール確認をスキップ
                # データ検証も無効化
                res = sb.auth.sign_up({
                    "email": email, 
                    "password": pw, 
                    "options": {
                        "email_confirm": False,
                        "data_validation": False
                    }
                })
                if res.user:
                    # 新規登録成功時もユーザーレコードを作成
                    ensure_user_record(sb, res.user)
                    st.success("登録完了！ログインしてください")
                else:
                    st.error("登録に失敗しました")
            except Exception as e:
                st.error(f"登録エラー: {str(e)}")
    st.stop()

# 4) 認証後：Session State からユーザー情報を取得
user = st.session_state.user
st.sidebar.success(f"ログイン中: {user.email}")

# ログイン後は、ユーザーレコードを確認
ensure_user_record(sb, user)

# 認証成功メッセージ
auth_method = st.session_state.get("auth_method", "email")
st.success(f"認証に成功しました（{auth_method}）！ダッシュボードに移動します...")

# アプリケーションの最後に配置
# ダッシュボードへの遷移（Google認証後も含む）
if st.session_state.get("redirect_to_dashboard"):
    # フラグをリセット（無限ループ防止）
    del st.session_state["redirect_to_dashboard"]
    
    # 二段階目：安定した状態からページ遷移
    try:
        st.switch_page("pages/dashboard.py")
    except Exception as e:
        st.error(f"ページ遷移エラー: {str(e)}")
        st.page_link("pages/dashboard.py", label="手動でダッシュボードへ", icon="🧭")