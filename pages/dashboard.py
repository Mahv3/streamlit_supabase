# pages/dashboard.py - ログイン後のダッシュボード

import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
from langchain.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document

# 環境変数のロード
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# デバッグ情報の表示
st.sidebar.write("セッション状態:", list(st.session_state.keys()))
st.sidebar.write("クエリパラメータ:", dict(st.query_params))

# クエリパラメータからトークンを取得
query_params = st.query_params
if "token" in query_params and "user" not in st.session_state:
    token = query_params["token"]
    try:
        sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = sb.auth.get_user(token)
        if res.user:
            st.session_state.user = res.user
            st.session_state.token = token
            st.sidebar.success("トークンから認証情報を復元しました")
            # クエリパラメータを削除するためリダイレクト
            st.markdown('''
            <script>
                window.history.replaceState({}, document.title, "/dashboard");
            </script>
            ''', unsafe_allow_html=True)
    except Exception as e:
        st.sidebar.error(f"トークン認証エラー: {str(e)}")

# 未認証の場合はホームページにリダイレクト
if "user" not in st.session_state:
    st.warning("ログインが必要です。ホームページに移動します...")
    st.markdown('<meta http-equiv="refresh" content="2; url=/">', unsafe_allow_html=True)
    st.stop()

# Supabase クライアント生成
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ユーザー情報を取得
user = st.session_state.user

# ダッシュボードUI
st.title("ドキュメント管理ダッシュボード")
st.sidebar.success(f"ログイン中: {user.email}")

# ログアウトボタン
if st.sidebar.button("ログアウト"):
    del st.session_state.user
    if "token" in st.session_state:
        del st.session_state.token
    st.sidebar.success("ログアウトしました")
    st.markdown('<meta http-equiv="refresh" content="1; url=/">', unsafe_allow_html=True)
    st.stop()

# LangChain 準備
try:
    emb = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
    vs = SupabaseVectorStore(
        client=sb,  # 既存のSupabaseクライアントを使用
        embedding=emb,
        table_name="documents"
    )

    # ドキュメント保存 UI
    st.header("ドキュメント保存")
    content = st.text_area("保存したいテキストを入力")
    if st.button("保存"):
        try:
            # add_texts メソッドを使用（最も簡単な方法）
            result = vs.add_texts(
                texts=[content],
                metadatas=[{"user_id": user.email}]
            )
            st.success("Supabase の documents テーブルに保存しました！")
        except Exception as e:
            st.error(f"保存エラー: {str(e)}")
            st.write("エラーの詳細:", type(e).__name__)
            
            # フォールバック方法を試す
            try:
                # Document オブジェクトを使用
                doc = Document(
                    page_content=content,
                    metadata={"user_id": user.email}
                )
                vs.add_documents([doc])
                st.success("代替方法で保存に成功しました！")
            except Exception as e2:
                st.error(f"代替方法でも失敗: {str(e2)}")

    # 保存済みドキュメントの表示
    try:
        st.header("保存済みドキュメント")
        # ユーザーのドキュメントを取得
        docs = sb.table("documents").select("*").execute()
        if docs.data:
            for doc in docs.data:
                with st.expander(f"ドキュメント {doc.get('id', '不明')}"):
                    st.write(doc.get('content', '') or doc.get('page_content', ''))
        else:
            st.info("保存されたドキュメントはありません")
    except Exception as e:
        st.warning(f"ドキュメント一覧の取得エラー: {str(e)}")

except Exception as e:
    st.error(f"LangChain初期化エラー: {str(e)}")