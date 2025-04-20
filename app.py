# streamlit_app.py

import os
from dotenv import load_dotenv
import streamlit as st
from supabase import create_client, Client
import urllib.parse
import time

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
    query_params = st.query_params
    
    # デバッグ情報
    st.sidebar.write("クエリパラメータ:", dict(query_params))
    
    # アクセストークンが含まれているか確認
    if "access_token" in query_params:
        st.sidebar.success("✓ アクセストークンを検出")
        access_token = query_params["access_token"]
        try:
            # アクセストークンを使用してログイン
            res = sb.auth.get_user(access_token)
            if res.user:
                st.sidebar.success("✓ ユーザー情報を取得")
                
                # セッションにユーザー情報を保存
                st.session_state.user = res.user
                st.session_state.token = access_token
                
                # ユーザーをユーザーテーブルに登録
                try:
                    ensure_user_record(sb, res.user)
                    st.sidebar.success("✓ ユーザープロファイル作成")
                except Exception as db_err:
                    st.sidebar.warning(f"プロファイル作成エラー (無視可): {str(db_err)}")
                
                # クエリパラメータを削除するためリダイレクト
                st.sidebar.info("ページを再読み込みします...")
                time.sleep(1)  # 少し待機して情報を表示
                st.rerun()
                return True
            else:
                st.sidebar.error("✗ ユーザー情報が取得できませんでした")
        except Exception as e:
            st.sidebar.error(f"✗ 認証エラー: {str(e)}")
    else:
        # URLハッシュフラグメント（#以降）からアクセストークンを取得するJavaScript
        st.markdown("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // URLハッシュがある場合
                if (window.location.hash) {
                    console.log("Hash detected:", window.location.hash);
                    
                    // #を除去
                    const hash = window.location.hash.substring(1);
                    
                    // URLパラメータを解析
                    const params = {};
                    hash.split('&').forEach(function(part) {
                        const item = part.split('=');
                        params[item[0]] = decodeURIComponent(item[1]);
                    });
                    
                    // アクセストークンがあれば
                    if (params.access_token) {
                        console.log("Access token found, redirecting...");
                        
                        // クエリパラメータとしてリダイレクト
                        window.location.href = window.location.pathname + "?access_token=" + params.access_token;
                    }
                }
            });
        </script>
        """, unsafe_allow_html=True)
    
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
                st.rerun()  # 新しいAPI
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

ensure_user_record(sb, user)


# 同一ファイルの続き

from langchain.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document  # Document クラスをインポート

# 6) LangChain 準備
emb = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
vs = SupabaseVectorStore(
    client=sb,  # 既存のSupabaseクライアントを使用
    embedding=emb,
    table_name="documents"
)

# 7) ドキュメント保存 UI
st.header("ドキュメント保存")
content = st.text_area("保存したいテキストを入力")
if st.button("保存"):
    # Document クラスのインスタンスを作成
    doc = Document(
        page_content=content,
        metadata={"user_id": user.email}  # idの代わりにemailを使用
    )
    # ドキュメントを追加
    vs.add_documents([doc])
    st.success("Supabase の documents テーブルに保存しました！")
