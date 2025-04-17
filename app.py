# streamlit_app.py

import os
from dotenv import load_dotenv
import streamlit as st
from supabase import create_client, Client

# 1) 環境変数ロード
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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

# 3) 認証判定＆ログインフォーム
if "user" not in st.session_state:
    st.title("ログイン or 新規登録")
    email = st.text_input("Email")
    pw    = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("ログイン"):
            res = sb.auth.sign_in(email=email, password=pw)
            if res.user:
                st.session_state.user = res.user
                st.experimental_rerun()
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
from langchain.vectorstores import SupabaseVectorStore

# 6) LangChain 準備
emb = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
vs  = SupabaseVectorStore(
    supabase_url=SUPABASE_URL,
    supabase_key=SUPABASE_KEY,
    embedding=emb,
    table_name="documents"
)

# 7) ドキュメント保存 UI
st.header("ドキュメント保存")
content = st.text_area("保存したいテキストを入力")
if st.button("保存"):
    vs.add_documents([{
        "page_content": content,
        "metadata": {"user_id": user.id}
    }])
    st.success("Supabase の documents テーブルに保存しました！")
