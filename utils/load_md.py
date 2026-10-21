import frontmatter  # Thư viện đọc file md có frontmatter

def load_prompt_template(file_path: str):
    """Hàm đọc file markdown chứa frontmatter và nội dung prompt"""
    with open(file_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    
    # Lấy thông số cấu hình (nếu muốn dùng động) và phần nội dung text
    config = post.metadata  # Ví dụ: {'model': 'gemini-2.5-flash', 'temperature': 0.1, ...}
    prompt_content = post.content
    
    return config, prompt_content