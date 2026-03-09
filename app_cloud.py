"""
업체 검색 웹 애플리케이션 - 클라우드 배포용 (Selenium 없음)
==========================================================
네이버 지역검색 API 기반
"""

import os
import re
import io
import time
import requests
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")


def clean_html(text):
    return re.sub(r"<[^>]+>", "", text).strip()


def search_naver_local(query, display=5):
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "start": 1, "sort": "random"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    body = request.get_json()
    keywords = body.get("keywords", [])
    regions = body.get("regions", [])

    if not keywords or not regions:
        return jsonify({"error": "업종과 지역을 선택해주세요."}), 400

    all_items = []
    seen = set()

    for keyword in keywords:
        for region in regions:
            query = f"{region} {keyword}"
            data = search_naver_local(query)

            if not data or "items" not in data:
                continue

            for item in data["items"]:
                title = clean_html(item.get("title", ""))
                telephone = item.get("telephone", "").strip()
                address = item.get("address", "").strip()
                road_address = item.get("roadAddress", "").strip()
                category = item.get("category", "").strip()
                link = item.get("link", "").strip()

                dup_key = f"{title}|{address}"
                if dup_key in seen:
                    continue
                seen.add(dup_key)

                all_items.append({
                    "업종": keyword,
                    "검색지역": region,
                    "상호": title,
                    "전화번호": telephone,
                    "지번주소": address,
                    "도로명주소": road_address,
                    "카테고리": category,
                    "링크": link,
                })

            time.sleep(0.2)

    by_keyword = {}
    for item in all_items:
        k = item["업종"]
        by_keyword[k] = by_keyword.get(k, 0) + 1

    return jsonify({
        "total": len(all_items),
        "items": all_items,
        "by_keyword": by_keyword,
    })


@app.route("/api/download", methods=["POST"])
def api_download():
    body = request.get_json()
    items = body.get("items", [])

    if not items:
        return jsonify({"error": "데이터가 없습니다."}), 400

    df = pd.DataFrame(items)

    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="업체목록.xlsx",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
