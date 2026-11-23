import os
import json
from datetime import datetime, timedelta
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
API_KEY = os.environ.get("ICN_API_KEY")

HOST = "apis." + "data.go.kr"
SERVICE_PATH = "B551177/statusOfAllFltDeOdp"
ENDPOINT_ARR = f"http://{HOST}/{SERVICE_PATH}/getFltArrivalsDeOdp"
ENDPOINT_DEP = f"http://{HOST}/{SERVICE_PATH}/getFltDeparturesDeOdp"

def get_date_range():
    kst_now = datetime.utcnow() + timedelta(hours=9)
    dates = []
    for offset in range(-1, 3):  # -1일 ~ +2일 (총 4일)
        target = kst_now + timedelta(days=offset)
        ymd = target.strftime("%Y%m%d")
        md = target.strftime("%m/%d")
        label = f"어제({md})" if offset == -1 else (f"오늘({md})" if offset == 0 else (f"내일({md})" if offset == 1 else f"+{offset}일({md})"))
        dates.append((ymd, label))
    return dates

def format_time(dt_str):
    if not dt_str or len(str(dt_str).strip()) < 12:
        return ""
    s = str(dt_str).strip()
    return f"{s[8:10]}:{s[10:12]}:00"

def fetch_and_save():
    if not API_KEY:
        raise ValueError("ICN_API_KEY 환경변수가 설정되지 않았습니다.")

    dates = get_date_range()
    new_records = []
    headers = {"User-Agent": "Mozilla/5.0"}

    for ymd, label in dates:
        for gubun, url in [("INBOUND", ENDPOINT_ARR), ("OUTBOUND", ENDPOINT_DEP)]:
            for poc_code, fixed_type in [("P", "여객"), ("C", "화물")]:
                params = {
                    "serviceKey": API_KEY, "searchDate": ymd,
                    "passengerOrCargo": poc_code, "numOfRows": 2500, "pageNo": 1, "type": "json",
                }
                res = requests.get(url, params=params, headers=headers, timeout=20, verify=False)
                res.raise_for_status()
                data = res.json()

                items = data.get("response", {}).get("body", {}).get("items", [])
                if isinstance(items, dict): items = items.get("item", [])
                if isinstance(items, dict): items = [items]

                for item in items:
                    cs_raw = str(item.get("codeshare") or "").strip()
                    master_id = str(item.get("masterFlightId") or "").strip()
                    is_cs = (cs_raw == "Slave") or bool(master_id)
                    flight_id = str(item.get("flightId") or "")
                    airline_code = str(item.get("airlineCode") or flight_id[:2])

                    airport_code = str(item.get("airportCode") or "")
                    dep_ap = airport_code if gubun == "INBOUND" else "ICN"
                    arr_ap = "ICN" if gubun == "INBOUND" else airport_code

                    remark_str = str(item.get("remark") or "").strip()
                    est_time = format_time(item.get("estimatedDatetime", ""))
                    etd_val, atd_val = ("", est_time) if remark_str in ["출발", "도착"] else (est_time, "")

                    new_records.append({
                        "일자": label, "항공사코드": airline_code, "항공사명": str(item.get("airline") or ""),
                        "편명": flight_id, "구분": gubun, "여객/화물": fixed_type,
                        "등록기호": str(item.get("aircraftRegNo") or ""), "기종": str(item.get("aircraftSubtype") or ""),
                        "출발지": dep_ap, "도착지": arr_ap, "STD/A": format_time(item.get("scheduleDatetime", "")),
                        "ETD/A": etd_val, "ATD/A": atd_val, "주기장": str(item.get("fstandPosition") or ""),
                        "현황": remark_str, "_is_cs": is_cs,
                    })

    kst_now_str = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    with open("flight_db.json", "w", encoding="utf-8") as f:
        json.dump({"updated_at": kst_now_str, "total_count": len(new_records), "records": new_records}, f, ensure_ascii=False)
    print(f"[{kst_now_str}] 수집 완료: {len(new_records)}건")

if __name__ == "__main__":
    fetch_and_save()
