from flask import Flask, request, jsonify
import re
import json

app = Flask(__name__)

# Emailを抽出する関数
def extract_email(text):
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else "不明"

# モバイルを抽出する関数
def extract_mobile(text):
    # 携帯電話番号のパターン（090・080・070）
    mobile_match = re.search(r'(\+?\d{1,3}[-.\s]?)?(0[789]0)[-().\s]?(\d{4})[-().\s]?(\d{4})', text)
    if mobile_match:
        return f"{mobile_match.group(2)}-{mobile_match.group(3)}-{mobile_match.group(4)}"
    
    return "不明"

# 電話番号を抽出する関数
def extract_phone(text):
    # # FAXを除外
    # if re.search(r'FAX|Fax|fax', text):
    #     return "不明"

    # 携帯電話のパターン（090, 080, 070）を除外
    text = re.sub(r'(\+?\d{1,3}[-.\s]?)?(0[789]0)[-().\s]?(\d{4})[-().\s]?(\d{4})', '', text)

    # 固定電話番号のパターン
    landline_match = re.search(r'(0\d{1,4})[-().\s（）]?(\d{1,4})[-().\s（）]?(\d{4})', text)
    if landline_match:
        full_number = f"{landline_match.group(1)}-{landline_match.group(2)}-{landline_match.group(3)}"
        if len(full_number.replace("-", "")) == 10:
            return full_number

    return "不明"

# 郵便番号を抽出する関数
def extract_postal_code(text):
    # 電話番号（TELやFAX）の場合、郵便番号としては抽出しない
    if re.search(r'(TEL|Tel|tel|Fax|FAX|MOBILE|Mobile|mobile|PHONE|phone|Phone|電話番号|携帯電話|携帯番号)', text):
        return "不明"  # "TEL"や"FAX"が含まれている場合は郵便番号を抽出しない
    
    # 電話番号と誤認されないように事前にチェック
    if re.search(r'(\+?\d{1,3}[-.\s]?)?(0[789]0)[-().\s]?(\d{4})[-().\s]?(\d{4})', text):
        return "不明"  # 電話番号と認識された場合、郵便番号としては抽出しない

    # 郵便番号の正規表現
    match = re.search(r'〒?\s*\d{3}[-－]?\d{4}', text)
    if match:
        postal_code = match.group(0).replace("－", "-").replace(" ", "")
        if not postal_code.startswith("〒"):
            postal_code = "〒" + postal_code
        return postal_code
    
    return "不明"

# 会社名を抽出する関数
def extract_company(text):
    match = re.search(r'''株式会社|有限会社|合同会社|合資会社|合名会社|
                      一般社団法人|一般財団法人|特定非営利活動法人|
                      NPO法人|学校法人|社会福祉法人|組合|Inc\.|Corp\.|LLC''', text)
    return text if match else "不明"

# 役職を抽出する関数
def extract_position(text):
    match = re.search(r'''代表取締役|取締役|社長|副社長|専務取締役|常務取締役|執行役員|
                      本部長|統括部長|部長|副部長|課長|課長代理|係長|リーダー|主任|
                      マネージャー|ゼネラルマネージャー|シニアマネージャー|
                      アシスタントマネージャー|プロジェクトマネージャー|
                      工場長|支店長|営業部長|開発部長|事務局長|理事|監査役|相談役|顧問''', text)
    return match.group(0) if match else "不明"

# 所属部署を抽出する関数
def extract_department(text):
    match = re.search(r'(\S*?(?:部|課|室|センター|チーム))', text)
    return match.group(0) if match else "不明"

# 住所を抽出する関数
def extract_address(text):
    # 都道府県を含むかチェック
    if not re.search(r'(東京都|北海道|(?:京都|大阪)府|.{2,3}県)', text):
        return "不明"
    
    # 郵便番号を削除
    address = re.sub(r'〒?\s*\d{3}[-－−]?\d{4}', '', text).strip()

    ### 1行下の文章を追加するか検討
    
    return address

# 氏名(漢字)を抽出する関数
def extract_name_kanji(text):
    if re.search(r'[ァ-ン]', text):  # カタカナが含まれている
        return "不明"
    hiragana_count = len(re.findall(r'[ぁ-ん]', text)) # ひらがなが4文字以上含まれている
    if hiragana_count >= 4:  
        return "不明"
    if re.search(r'[a-zA-Z]', text):  # アルファベットが含まれている
        return "不明"
    if re.search(r'[!-/:-@[-`{-~]', text):  # 記号が含まれている
        return "不明"
    if re.search(r'社|所|部|課|士', text):  # 特定の文字が含まれている
        return "不明"
    match = re.search(r'([\u4E00-\u9FAF]{2,6})', text)
    text = text.replace(" ", "").replace("　", "")
    return text if match else "不明"


# 名刺情報を解析する関数
def parse_business_card(text):
    lines = text.split('\n')
    data = {
        "会社名": "不明",
        "郵便番号1": "不明",
        "住所1": "不明",
        "郵便番号2": "不明",
        "住所2": "不明",
        "氏名(漢字)": "不明",
        "氏名(カナ)": "不明", # 氏名(カナ)は常に不明とする
        "所属部署": "不明",
        "役職": "不明",
        "携帯番号": "不明",
        "電話番号": "不明",
        "Email": "不明",
    }
    
    filtered_lines = lines.copy()
    
    # 各行を解析し、適合した情報を取得してリストから削除
    for line in lines:
        if data["Email"] == "不明":
            data["Email"] = extract_email(line)
            if data["Email"] != "不明":
                filtered_lines.remove(line)
                continue
        
        if data["郵便番号1"] == "不明":
            data["郵便番号1"] = extract_postal_code(line) # 同じ行に住所がある可能性あるからcontinueしない
            if data["郵便番号1"] != "不明":
                filtered_lines.remove(line)

        if data["住所1"] == "不明":
            data["住所1"] = extract_address(line)
            if data["住所1"] != "不明":
                # error回避：すでに削除済みの可能性あり、以下も同様
                try:
                    filtered_lines.remove(line)
                except ValueError:
                    pass
                continue
        
        if data["郵便番号2"] == "不明":
            if data["郵便番号1"] != extract_postal_code(line):
                data["郵便番号2"] = extract_postal_code(line) # 同じ行に住所がある可能性あるからcontinueしない
                if data["郵便番号2"] != "不明":
                    filtered_lines.remove(line)

        if data["住所2"] == "不明":
            data["住所2"] = extract_address(line)
            if data["住所2"] != "不明":
                try:
                    filtered_lines.remove(line)
                except ValueError:
                    pass
                continue
        
        if data["携帯番号"] == "不明":
            data["携帯番号"] = extract_mobile(line) # 同じ行に電話番号がある可能性あるからcontinueしない
            if data["携帯番号"] != "不明":
                try:
                    filtered_lines.remove(line)
                except ValueError:
                    pass

        if data["電話番号"] == "不明":
            data["電話番号"] = extract_phone(line)
            if data["電話番号"] != "不明":
                try:
                    filtered_lines.remove(line)
                except ValueError:
                    pass
                continue
        
        if data["会社名"] == "不明":
            data["会社名"] = extract_company(line)
            if data["会社名"] != "不明":
                filtered_lines.remove(line)
                continue
        
        if data["役職"] == "不明":
            data["役職"] = extract_position(line) # 同じ行に所属部署がある可能性あるからcontinueしない
            if data["役職"] != "不明":
                filtered_lines.remove(line)

        
        if data["所属部署"] == "不明":
            data["所属部署"] = extract_department(line)
            if data["所属部署"] != "不明":
                try:
                    filtered_lines.remove(line)
                except ValueError:
                    pass
                continue

    # 削除されていない行から氏名(漢字)として抽出
    for line in filtered_lines:
        if data["氏名(漢字)"] == "不明":
            data["氏名(漢字)"] = extract_name_kanji(line)

    return data

# メイン関数をAPI化
@app.route('/main', methods=['POST'])
def main():
    try:
        # リクエストからJSONデータを取得
        request_data = request.get_json()

        # rowを取得
        row = request_data.get('row')

        # デコード処理：受け取った文字列に対してエンコードを解く
        value = json.loads(json.dumps(request_data['value'], ensure_ascii=False))

        if not value:
            return jsonify({"error": "Value is required"}), 400

        # 名刺情報を解析
        parsed_data = parse_business_card(value)
        # 辞書の値だけをリストに抽出
        values_only = list(parsed_data.values())

        # 解析結果を返す
        return jsonify(values_only)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
