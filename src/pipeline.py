"""
Main Pipeline: Orchestrates Botanical Scout -> Game Transformer -> Alchemy Validator.
Supports:
- Mode "fill": Cào cho đủ tổng số lượng N.
- Mode "add": Cào thêm N thảo dược mới.
- Option "retransform": Tự động game hóa lại toàn bộ dữ liệu thô đã cào khi thay đổi rule.
- Automatic batching, alias-aware deduplication, ID collision resolution, and backoff retries.
"""

import os
import sys
import json
import csv
from typing import List, Optional, Dict, Any

from src.models.schemas import RawBotanyBatch, RawBotanyMaterial
from src.agents.botanical_scout import run_botanical_scout, load_existing_raw_materials
from src.agents.game_transformer import run_game_transformer, load_existing_game_materials
from src.agents.alchemy_validator import run_alchemy_validator


def export_to_csv(materials_path: str, locale_path: str, csv_path: str):
    """Xuất file CSV tổng hợp để xem dữ liệu dạng bảng tra cứu dễ dàng."""
    if not os.path.exists(materials_path) or not os.path.exists(locale_path):
        return

    with open(materials_path, "r", encoding="utf-8") as f:
        materials = json.load(f)
    with open(locale_path, "r", encoding="utf-8") as f:
        locales = json.load(f)

    headers = [
        "ID", "Tên Hiển Thị", "Phẩm Cấp", "Nơi Sinh", "Khí Hậu", "Ngũ Hành", "Dược Tính",
        "Dược Lực Gốc", "Số Năm Sinh Trưởng", "Công Dụng Chính", "Công Dụng Ẩn", "Mô Tả"
    ]

    rows = []
    for mat in materials:
        name = locales.get(mat.get("name_key"), mat.get("name_key"))
        desc = locales.get(mat.get("desc_key"), mat.get("desc_key"))
        grade = locales.get(mat.get("grade_key"), mat.get("grade_key"))
        habitat = locales.get(mat.get("habitat_key"), mat.get("habitat_key"))
        climate = locales.get(mat.get("climate_key"), mat.get("climate_key"))
        element = locales.get(mat.get("element_key"), mat.get("element_key"))
        nature = locales.get(mat.get("nature_key"), mat.get("nature_key"))
        years_range = mat.get("growth_years_range", [0, 0])
        years = f"{years_range[0]} - {years_range[1]} năm"
        
        main_effs = "; ".join([
            f"{locales.get(e.get('effect_key'), e.get('effect_key'))} (x{e.get('weight')})"
            for e in mat.get("main_effects", [])
        ])
        hidden_effs = "; ".join([
            f"{locales.get(e.get('effect_key'), e.get('effect_key'))} ({int(e.get('trigger_chance', 0)*100)}%)"
            for e in mat.get("hidden_effects", [])
        ])

        rows.append([
            mat.get("id"), name, grade, habitat, climate, element, nature,
            mat.get("base_potency"), years, main_effs, hidden_effs, desc
        ])

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"[Pipeline] Đã xuất file CSV tổng hợp tra cứu -> {csv_path}")


def run_pipeline(
    mode: str = "fill",
    amount: int = 100,
    batch_size: int = 10,
    force_retransform: bool = False,
    delay_between_batches: float = 2.0,
    raw_path: str = "outputs/raw/botany_raw.json",
    processed_path: str = "outputs/processed/materials.json",
    locale_path: str = "outputs/locales/vi.json",
    csv_path: str = "outputs/processed/materials_summary.csv"
) -> Dict[str, Any]:
    """
    Điều phối toàn bộ Pipeline:
    - Nếu force_retransform=True: Bỏ qua cào mới, áp dụng rule mới cho toàn bộ dữ liệu thô đã có.
    - Nếu force_retransform=False:
      * Bước 1 (Agent 1): Cào thảo dược thực tế (kiểm tra bí danh trùng lặp, chia batch, dừng khi đủ/lỗi).
      * Bước 2 (Agent 2): Game hóa các thảo dược mới cào sang mã Key và cập nhật vi.json (chống trùng ID).
      * Bước 3 (Agent 3): Kiểm chuẩn Schema, đối soát Key và mô phỏng đan đạo.
      * Bước 4: Xuất file CSV tra cứu.
    """
    print("=" * 65)
    print("  KHỞI CHẠY PIPELINE DỮ LIỆU GAME THẢO DƯỢC & ĐAN ĐẠO (MULTI-AGENT)")
    if force_retransform:
        print("  Chế độ: ĐỒNG BỘ LẠI RULE MỚI CHO TOÀN BỘ DỮ LIỆU ĐÃ CÀO")
    else:
        print(f"  Chế độ: {'CÀO CHO ĐỦ TỔNG SỐ' if mode == 'fill' else 'CÀO THÊM'} {amount} THẢO DƯỢC")
    print(f"  Kích thước Batch: {batch_size} thảo dược / lần gọi")
    print("=" * 65)

    if force_retransform:
        # Chế độ đồng bộ lại rule mới cho toàn bộ dữ liệu thô đã có
        raw_materials = load_existing_raw_materials(raw_path)
        if not raw_materials:
            print("[Cảnh báo] Kho dữ liệu thô chưa có thảo dược nào để đồng bộ lại!")
            return {"status": "EMPTY_RAW_DATA"}
        newly_crawled_count = 0
        crawl_status = "SKIPPED_RETRANSFORM_ONLY"
    else:
        # Bước 1: AGENT 1 - Thu thập dữ liệu thực tế
        raw_materials, newly_crawled_count, crawl_status = run_botanical_scout(
            mode=mode,
            amount=amount,
            batch_size=batch_size,
            delay_between_batches=delay_between_batches,
            raw_path=raw_path
        )

        if crawl_status == "ALREADY_FULL":
            print(f"\n[Thông báo] Hệ thống đã có đủ số lượng yêu cầu ({len(raw_materials)}/{amount}). Không cần cào thêm dữ liệu thô.")
        elif crawl_status == "ERROR_OR_TOKEN_LIMIT":
            print(f"\n[Cảnh báo] Quá trình cào dừng sớm do giới hạn API/Token hoặc lỗi mạng. Hiện có {len(raw_materials)} thảo dược thô.")
        elif crawl_status == "NO_MORE_DATA":
            print(f"\n[Thông báo] Không tìm thấy thêm thảo dược mới nào chưa trùng lặp. Hiện có {len(raw_materials)} thảo dược thô.")
        else:
            print(f"\n[Thành công] Đã cào đủ số lượng thảo dược yêu cầu! Tổng kho thô: {len(raw_materials)} cây.")

    # Bước 2: AGENT 2 - Game hóa dữ liệu
    print("\n" + "-" * 50)
    print("[Pipeline -> Bước 2] Chuyển giao dữ liệu cho Agent 2 (Game Transformer)...")
    game_materials = run_game_transformer(
        raw_materials=raw_materials,
        batch_size=batch_size,
        force_retransform=force_retransform,
        delay_between_batches=delay_between_batches,
        processed_output_path=processed_path,
        locale_output_path=locale_path
    )

    # Bước 3: AGENT 3 - Kiểm chuẩn & Mô phỏng đan đạo
    print("\n" + "-" * 50)
    print("[Pipeline -> Bước 3] Chuyển giao dữ liệu cho Agent 3 (QA & Alchemy Validator)...")
    qa_report = run_alchemy_validator(
        materials_path=processed_path,
        locale_path=locale_path
    )

    # Bước 4: Xuất CSV tổng hợp tra cứu
    print("\n" + "-" * 50)
    print("[Pipeline -> Bước 4] Xuất bảng tra cứu tổng hợp...")
    export_to_csv(
        materials_path=processed_path,
        locale_path=locale_path,
        csv_path=csv_path
    )

    print("\n" + "=" * 65)
    print("  KẾT THÚC PIPELINE THÀNH CÔNG!")
    print(f"  - Tổng thảo dược thô (raw): {len(raw_materials)}")
    print(f"  - Tổng thảo dược Game đã chuẩn hóa: {len(game_materials)}")
    print(f"  - Trạng thái cào: {crawl_status}")
    print(f"  - Schema Pass Rate: {qa_report['schema_pass_rate'] * 100}%")
    print(f"  - Localization Parity Rate: {qa_report['localization_parity_rate'] * 100}%")
    print("=" * 65)

    return {
        "raw_count": len(raw_materials),
        "game_materials_count": len(game_materials),
        "newly_crawled_count": newly_crawled_count,
        "crawl_status": crawl_status,
        "qa_report": qa_report
    }


if __name__ == "__main__":
    run_pipeline()
