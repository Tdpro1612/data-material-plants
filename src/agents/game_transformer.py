"""
Agent 2: Game Transformer & Key Architect
Transforms raw botany data into game materials with localization keys.
Supports batching, ID collision avoidance, exponential backoff, and full re-transformation when rules change.
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Set, Callable
import frontmatter
from google import genai
from dotenv import load_dotenv

from src.models.schemas import (
    RawBotanyBatch, RawBotanyMaterial, GameMaterial, GameTransformerOutput
)

load_dotenv()


def load_agent_prompt(agent_path: str = ".agents/game_transformer.md"):
    with open(agent_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    return post.metadata, post.content


def call_with_backoff(api_call_fn: Callable[[], Any], max_retries: int = 4, base_delay: float = 2.0) -> Any:
    """Gọi hàm API kèm cơ chế tự động thử lại (Retry with Exponential Backoff)."""
    for attempt in range(1, max_retries + 1):
        try:
            return api_call_fn()
        except Exception as e:
            if attempt == max_retries:
                raise e
            wait_time = base_delay * (2 ** (attempt - 1))
            print(f"  [Agent 2 API Cảnh Báo] Gặp sự cố ('{e}'). Đang nghỉ và thử lại lần {attempt}/{max_retries} sau {wait_time:.1f}s...")
            time.sleep(wait_time)


def update_locale_file(locale_path: str, new_entries: Dict[str, str]):
    """Merge các cặp key-value mới vào file locale hiện có."""
    existing_data = {}
    if os.path.exists(locale_path):
        try:
            with open(locale_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"[Cảnh báo] Không thể đọc {locale_path}, sẽ tạo mới: {e}")

    existing_data.update(new_entries)

    os.makedirs(os.path.dirname(locale_path), exist_ok=True)
    with open(locale_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)


def load_existing_game_materials(processed_path: str = "outputs/processed/materials.json") -> List[GameMaterial]:
    """Đọc danh sách game materials đã được xử lý trước đó."""
    if not os.path.exists(processed_path):
        return []
    try:
        with open(processed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [GameMaterial.model_validate(item) for item in data]
    except Exception as e:
        print(f"[Cảnh báo] Lỗi khi đọc {processed_path}: {e}")
        return []


def save_game_materials(materials: List[GameMaterial], processed_path: str = "outputs/processed/materials.json"):
    """Lưu danh sách game materials vào file JSON."""
    os.makedirs(os.path.dirname(processed_path), exist_ok=True)
    with open(processed_path, "w", encoding="utf-8") as f:
        materials_data = [m.model_dump() for m in materials]
        json.dump(materials_data, f, ensure_ascii=False, indent=2)


def transform_single_batch(
    client: genai.Client,
    model_name: str,
    system_instruction: str,
    raw_sublist: List[RawBotanyMaterial]
) -> GameTransformerOutput:
    """Gọi Gemini API để chuyển đổi 1 sub-batch nguyên liệu thô sang game format kèm backoff."""
    sub_batch = RawBotanyBatch(materials=raw_sublist)
    prompt_user = f"""
    Hãy game hóa danh sách thảo dược thực tế sau đây theo đúng các quy tắc trong system instruction:
    {sub_batch.model_dump_json(indent=2)}

    YÊU CẦU QUAN TRỌNG:
    1. Định danh id: mat_<ten_khong_dau> (ví dụ: mat_nhan_sam).
    2. name_key = "<id>_name", desc_key = "<id>_desc".
    3. QUY TẮC ĐẶT TÊN TRONG locale_entries: BẮT BUỘC giữ tên dược liệu chuẩn xác, thanh lịch và trang nhã theo y học cổ truyền (ví dụ: "Nhân Sâm", "Linh Chi", "Hà Thủ Ô Đỏ", "Ba Kích", "Kê Huyết Đằng", "Đương Quy", "Hoàng Kỳ"...). TUYỆT ĐỐI KHÔNG tự tiện bịa hoặc ghép thêm các từ ngữ cải lương, sáo rỗng như: "thần nấm", "thiên niên", "thần căn", "huyết căn", "hồi dương", "phong thảo", "thần thảo"... làm tên vị thuốc bị lởm và mất tính chân thực. Linh Chi là Linh Chi, Nhân Sâm là Nhân Sâm!
    4. Ánh xạ chính xác habitat_key, climate_key, element_key, nature_key theo đúng danh mục Enum.
    5. Phân tách rõ ràng Sinh Khí (HP) và Nguyên Khí (MP) trong main_effects (1 đến 5 công dụng chính).
    6. Chọn 1 đến 3 công dụng ẩn trong hidden_effects kèm trigger_chance.
    7. Trả về đồng thời locale_entries chứa các đối tượng {{"key": "<mã_key>", "value": "<bản_dịch>"}} cho <id>_name và <id>_desc. Mô tả sinh động bám sát đặc trưng rễ, thân, lá của dược liệu thực tế, tự nhiên và không sáo rỗng.
    """

    def _execute():
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_user,
            config=dict(
                system_instruction=system_instruction,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=GameTransformerOutput,
            )
        )
        return GameTransformerOutput.model_validate_json(response.text)

    return call_with_backoff(_execute)


def resolve_id_collisions(
    new_materials: List[GameMaterial],
    locale_dict: Dict[str, str],
    existing_ids: Set[str]
) -> List[GameMaterial]:
    """
    Tự động kiểm tra và giải quyết xung đột mã ID:
    Nếu ID đã tồn tại trong kho, tự động thêm hậu tố (_2, _3...) và đồng bộ lại key bản dịch.
    """
    for mat in new_materials:
        orig_id = mat.id
        if orig_id in existing_ids:
            counter = 2
            candidate_id = f"{orig_id}_{counter}"
            while candidate_id in existing_ids:
                counter += 1
                candidate_id = f"{orig_id}_{counter}"

            print(f"  [Xử lý trùng ID]: Đổi '{orig_id}' -> '{candidate_id}'")
            
            old_name_key = mat.name_key
            old_desc_key = mat.desc_key
            
            mat.id = candidate_id
            mat.name_key = f"{candidate_id}_name"
            mat.desc_key = f"{candidate_id}_desc"

            # Cập nhật lại trong từ điển bản dịch
            if old_name_key in locale_dict:
                locale_dict[mat.name_key] = locale_dict.pop(old_name_key)
            if old_desc_key in locale_dict:
                locale_dict[mat.desc_key] = locale_dict.pop(old_desc_key)

        existing_ids.add(mat.id)

    return new_materials


def run_game_transformer(
    raw_materials: List[RawBotanyMaterial],
    batch_size: int = 10,
    force_retransform: bool = False,
    delay_between_batches: float = 2.0,
    processed_output_path: str = "outputs/processed/materials.json",
    locale_output_path: str = "outputs/locales/vi.json"
) -> List[GameMaterial]:
    """
    Chuyển đổi dữ liệu thô sang GameMaterial và bổ sung bản dịch vào vi.json theo từng batch.
    - force_retransform=False: Chỉ xử lý những thảo dược thô chưa được game hóa.
    - force_retransform=True: Game hóa lại TOÀN BỘ thảo dược thô theo rule/prompt mới.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY không được tìm thấy trong .env!")

    client = genai.Client(api_key=api_key)
    metadata, system_instruction = load_agent_prompt()
    model_name = metadata.get("model", "gemini-2.5-flash")
    if "3.8" in model_name:
        model_name = "gemini-2.5-flash"

    # Kiểm tra chế độ retransform
    if force_retransform:
        print("[Agent 2: Game Transformer] CHẾ ĐỘ ĐỒNG BỘ RULE MỚI: Xóa cache Game Material và chuyển đổi lại từ đầu toàn bộ dữ liệu thô...")
        existing_game_materials: List[GameMaterial] = []
        unprocessed_raw = raw_materials
    else:
        existing_game_materials = load_existing_game_materials(processed_output_path)
        current_game_count = len(existing_game_materials)
        total_raw_count = len(raw_materials)

        if current_game_count >= total_raw_count:
            print(f"[Agent 2: Game Transformer] Tất cả {total_raw_count} thảo dược thô đều đã được Game hóa. Không có gì cần chuyển đổi.")
            return existing_game_materials

        unprocessed_raw = raw_materials[current_game_count:]
        print(f"[Agent 2: Game Transformer] Phát hiện {len(unprocessed_raw)} thảo dược thô mới cần Game Hóa...")

    existing_ids: Set[str] = {m.id for m in existing_game_materials}

    # Chia batch để gọi Agent 2
    for i in range(0, len(unprocessed_raw), batch_size):
        chunk = unprocessed_raw[i : i + batch_size]
        batch_idx = (i // batch_size) + 1
        total_chunks = ((len(unprocessed_raw) - 1) // batch_size) + 1
        print(f"[Agent 2] -> Đang game hóa Batch {batch_idx}/{total_chunks} ({len(chunk)} thảo dược)...")

        try:
            trans_result = transform_single_batch(
                client=client,
                model_name=model_name,
                system_instruction=system_instruction,
                raw_sublist=chunk
            )
        except Exception as e:
            print(f"[Agent 2: Lỗi khi Game hóa Batch {batch_idx}]: {e}")
            break

        # Bóc tách bản dịch
        locale_dict = {entry.key: entry.value for entry in trans_result.locale_entries}

        # Kiểm tra và xử lý chống trùng ID
        safe_materials = resolve_id_collisions(
            new_materials=trans_result.materials,
            locale_dict=locale_dict,
            existing_ids=existing_ids
        )

        # 1. Cập nhật locale vi.json
        update_locale_file(locale_output_path, locale_dict)

        # 2. Append vào existing_game_materials và lưu ngay lập tức
        existing_game_materials.extend(safe_materials)
        save_game_materials(existing_game_materials, processed_output_path)
        print(f"[Agent 2] Đã game hóa thành công Batch {batch_idx}. Tổng Game Materials hiện có: {len(existing_game_materials)}")

        # Delay giữa các batch
        if (i + batch_size) < len(unprocessed_raw) and delay_between_batches > 0:
            time.sleep(delay_between_batches)

    return existing_game_materials
