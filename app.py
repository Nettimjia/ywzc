from flask import Flask, render_template, jsonify, request
import requests
import re
from datetime import datetime
import os

app = Flask(__name__)

# ── 对接外部 API ────────────────────────────────────────

API_URL = 'https://www.ywygzc.com/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew'
API_HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.ywygzc.com/recommend_project_notice.html',
    'Origin': 'https://www.ywygzc.com',
}


def clean_html(text):
    return re.sub(r'<[^>]+>', '', text or '')


def fetch_api(keyword, page=0, size=100):
    param = {
        'token': '', 'pn': page, 'rn': size,
        'sdt': '', 'edt': '', 'wd': keyword,
        'inc_wd': '', 'exc_wd': '', 'fields': 'title',
        'cnum': '', 'sort': '{"webdate":"0"}', 'ssort': 'title',
        'cl': 500, 'terminal': '', 'condition': [],
        'time': None, 'highlights': 'title',
        'statistics': None, 'unionCondition': None,
        'accuracy': '', 'noParticiple': '0', 'searchRange': None,
    }
    try:
        r = requests.post(API_URL, json=param, headers=API_HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'API 请求失败 [{keyword}]: {e}')
        return None


def parse_records(data):
    result = []
    records = (data or {}).get('result', {}).get('records', [])
    seen = set()
    for rec in records:
        infoid = rec.get('infoid', '')
        if infoid in seen:
            continue
        seen.add(infoid)
        linkurl = rec.get('linkurl', '')
        url = f"https://www.ywygzc.com{linkurl}" if linkurl.startswith('/') else linkurl
        result.append({
            'id':           infoid or linkurl,
            'company':      rec.get('infoa', '').strip() or '未知企业',
            'title':        clean_html(rec.get('title', '')),
            'publish_time': rec.get('webdate', ''),
            'url':          url,
        })
    return result


# ── Flask 路由 ──────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/search')
def api_search():
    """搜索接口：直接调外部API，不存数据库"""
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        # 无关键词时用默认关键词"采购"拉取一批数据
        keyword = '采购'
    
    data = fetch_api(keyword)
    items = parse_records(data)
    
    # 按发布时间排序
    items.sort(key=lambda x: x['publish_time'] or '', reverse=True)
    
    return jsonify({'success': True, 'count': len(items), 'data': items})


@app.route('/api/refresh')
def api_refresh():
    """刷新接口：用多个关键词批量采集"""
    keywords = ['采购', '项目', '招标', '服务', '工程',
                '广告', '推广', '朋友圈', '抖音', '媒体', '成交']
    all_items, seen = [], set()
    for kw in keywords:
        items = parse_records(fetch_api(kw))
        for item in items:
            if item['id'] not in seen:
                seen.add(item['id'])
                all_items.append(item)
    
    # 按发布时间排序
    all_items.sort(key=lambda x: x['publish_time'] or '', reverse=True)
    
    return jsonify({
        'success': True,
        'count': len(all_items),
        'message': f'成功采集 {len(all_items)} 条公告',
        'data': all_items
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
