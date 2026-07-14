"""测试 API:验证产品品类识别和成分出处"""
import httpx

# 读取护肤乳测试图片
with open(r'E:\AI-generated_files\program\2026_07_08_rihua_production\pictures\洗发露.jpg', 'rb') as f:
    image_bytes = f.read()

print(f'图片大小: {len(image_bytes)/1024:.0f} KB')

# 调用 API
files = {'image': ('test.jpg', image_bytes, 'image/jpeg')}
try:
    with httpx.Client(timeout=120) as client:
        resp = client.post('http://localhost:8000/api/analyze', files=files)
    print(f'状态码: {resp.status_code}')
    if resp.status_code != 200:
        print(f'错误详情: {resp.text}')
        import sys
        sys.exit(1)
    data = resp.json()

    print(f'\n=== 产品品类 ===')
    print(f'  {data.get("product_type", "无")}')

    print(f'\n=== OCR 识别文本(前200字) ===')
    print(data.get('ocr_text', '无')[:200])

    ingredients = data.get('ingredients', [])
    print(f'\n=== 成分列表 ({len(ingredients)} 个) ===')
    for ing in ingredients:
        db = '✓库' if ing.get('in_database') else '✗未'
        risk = ing.get('risk_level') or ''
        ref = ing.get('reference') or ''
        ref_short = ref[:50] + '...' if len(ref) > 50 else ref
        print(f'  [{db}] {ing["name"]:20s} | {risk:4s} | {ref_short}')

    print(f'\n=== 优点 ===')
    for p in data.get('pros', []):
        print(f'  + {p}')

    print(f'\n=== 缺点 ===')
    for c in data.get('cons', []):
        print(f'  - {c}')

    print(f'\n=== 评分 ===')
    print(f'  {data.get("score", "无")}/100')

    print(f'\n=== 总结 ===')
    print(data.get('summary', '无'))

except Exception as e:
    print(f'错误: {type(e).__name__}: {e}')
