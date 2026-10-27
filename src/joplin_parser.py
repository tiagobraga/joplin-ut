"""
Joplin Item Serializer & Parser
Compatível com a especificação oficial de texto plano do Joplin.
"""

import html
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

# Tipos de itens padrão do Joplin (ModelType oficial)
TYPE_NOTE = 1
TYPE_FOLDER = 2
TYPE_SETTING = 3
TYPE_RESOURCE = 4
TYPE_TAG = 5
TYPE_NOTE_TAG = 6

def generate_joplin_id() -> str:
    """Gera um UUID de 32 caracteres hexadecimais compatível com o Joplin."""
    return uuid.uuid4().hex

def format_iso_time(dt: Optional[datetime] = None) -> str:
    """Formata timestamp no padrão ISO 8601 UTC do Joplin."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

def parse_joplin_file(content: str) -> Dict[str, Any]:
    """
    Desempacota o conteúdo bruto de um arquivo .md do Joplin em:
    - title: Título da nota/caderno
    - body: Conteúdo markdown
    - metadata: Dicionário com id, parent_id, created_time, updated_time, type_, etc.
    """
    lines = content.splitlines()
    if not lines:
        return {"title": "", "body": "", "metadata": {}}

    # Procura onde o bloco de metadados começa a partir do final
    # No Joplin, todos os metadados no rodapé seguem a sintaxe 'chave: valor'
    meta_regex = re.compile(r"^([a-zA-Z0-9_]+):\s*(.*)$")
    
    idx = len(lines) - 1
    # Pula linhas vazias no fim do arquivo
    while idx >= 0 and not lines[idx].strip():
        idx -= 1

    metadata_lines = []
    # Coleta TODAS as linhas consecutivas de chave: valor
    # (normaliza '\_' caso o editor web do Nextcloud tenha escapado 'type\_: 1')
    while idx >= 0:
        line = lines[idx].replace("\\_", "_")
        match = meta_regex.match(line)
        if match:
            metadata_lines.insert(0, line)
            idx -= 1
        else:
            break

    # O que resta antes dos metadados é o título e o corpo da nota
    content_lines = lines[:idx + 1]
    
    # Processa os metadados
    metadata = {}
    for line in metadata_lines:
        match = meta_regex.match(line)
        if match:
            k, v = match.group(1), match.group(2)
            # Converte valores numéricos padrão
            if k in ("type_", "is_todo", "todo_completed", "is_conflict", "encryption_applied", "order", "deleted_time"):
                try:
                    metadata[k] = int(v)
                except ValueError:
                    metadata[k] = v
            else:
                metadata[k] = v

    # Separa título e corpo
    item_type = metadata.get("type_", TYPE_NOTE)
    
    if item_type in (TYPE_FOLDER, TYPE_TAG):
        # Para cadernos/pastas e tags, a primeira linha de texto é o nome
        title = content_lines[0].strip() if content_lines else metadata.get("title", "Sem Nome")
        body = ""
    elif item_type == TYPE_NOTE_TAG:
        title = ""
        body = ""
    else:
        # Para notas, primeira linha é título, o resto é o corpo
        if content_lines:
            title = content_lines[0].strip()
            # Pula linhas em branco imediatamente após o título
            body_start = 1
            if len(content_lines) > 1 and not content_lines[1].strip():
                body_start = 2
            body = "\n".join(content_lines[body_start:]).rstrip()
        else:
            title = metadata.get("title", "")
            body = ""

    return {
        "title": title,
        "body": body,
        "metadata": metadata
    }

def serialize_joplin_note(
    note_id: str,
    parent_id: str,
    title: str,
    body: str,
    created_time: Optional[str] = None,
    updated_time: Optional[str] = None,
    is_todo: int = 0,
    todo_completed: int = 0
) -> str:
    """Serializa uma nota no padrão exato do Joplin."""
    now_str = format_iso_time()
    c_time = created_time or now_str
    u_time = updated_time or now_str

    metadata_block = [
        f"id: {note_id}",
        f"parent_id: {parent_id or ''}",
        f"created_time: {c_time}",
        f"updated_time: {u_time}",
        "is_conflict: 0",
        "latitude: 0.00000000",
        "longitude: 0.00000000",
        "altitude: 0.0000",
        "author: ",
        "source_url: ",
        f"is_todo: {int(is_todo)}",
        "todo_due: 0",
        f"todo_completed: {int(todo_completed)}",
        "source: joplin-ut",
        "source_application: com.ubuntu.touch.joplin-ut",
        "application_data: ",
        "order: 0",
        f"user_created_time: {c_time}",
        f"user_updated_time: {u_time}",
        "encryption_cipher_text: ",
        "encryption_applied: 0",
        "markup_language: 1",
        "is_shared: 0",
        "share_id: ",
        "conflict_original_id: ",
        "master_key_id: ",
        "user_data: ",
        "deleted_time: 0",
        f"type_: {TYPE_NOTE}"
    ]

    parts = []
    if title:
        parts.append(title)
        parts.append("")
    if body:
        parts.append(body)
        parts.append("")
    parts.append("\n".join(metadata_block))

    return "\n".join(parts)

def serialize_joplin_folder(
    folder_id: str,
    title: str,
    parent_id: str = "",
    created_time: Optional[str] = None,
    updated_time: Optional[str] = None
) -> str:
    """Serializa um caderno/pasta no padrão exato do Joplin."""
    now_str = format_iso_time()
    c_time = created_time or now_str
    u_time = updated_time or now_str

    metadata_block = [
        f"id: {folder_id}",
        f"parent_id: {parent_id or ''}",
        f"created_time: {c_time}",
        f"updated_time: {u_time}",
        f"user_created_time: {c_time}",
        f"user_updated_time: {u_time}",
        "encryption_cipher_text: ",
        "encryption_applied: 0",
        "is_shared: 0",
        "share_id: ",
        "master_key_id: ",
        "user_data: ",
        "deleted_time: 0",
        f"type_: {TYPE_FOLDER}"
    ]

    parts = [
        title,
        "",
        "\n".join(metadata_block)
    ]
    return "\n".join(parts)


def serialize_joplin_tag(
    tag_id: str,
    title: str,
    created_time: Optional[str] = None,
    updated_time: Optional[str] = None
) -> str:
    """Serializa uma tag (type_: 5) no padrão exato do Joplin."""
    now_str = format_iso_time()
    c_time = created_time or now_str
    u_time = updated_time or now_str

    metadata_block = [
        f"id: {tag_id}",
        f"created_time: {c_time}",
        f"updated_time: {u_time}",
        f"user_created_time: {c_time}",
        f"user_updated_time: {u_time}",
        "encryption_cipher_text: ",
        "encryption_applied: 0",
        "is_shared: 0",
        "parent_id: ",
        "user_data: ",
        f"type_: {TYPE_TAG}"
    ]

    parts = [
        title.strip(),
        "",
        "\n".join(metadata_block)
    ]
    return "\n".join(parts)


def serialize_joplin_note_tag(
    assoc_id: str,
    note_id: str,
    tag_id: str,
    created_time: Optional[str] = None,
    updated_time: Optional[str] = None
) -> str:
    """Serializa um vínculo nota-tag (type_: 6) no padrão exato do Joplin."""
    now_str = format_iso_time()
    c_time = created_time or now_str
    u_time = updated_time or now_str

    metadata_block = [
        f"id: {assoc_id}",
        f"note_id: {note_id}",
        f"tag_id: {tag_id}",
        f"created_time: {c_time}",
        f"updated_time: {u_time}",
        f"user_created_time: {c_time}",
        f"user_updated_time: {u_time}",
        "encryption_cipher_text: ",
        "encryption_applied: 0",
        "is_shared: 0",
        f"type_: {TYPE_NOTE_TAG}"
    ]
    return "\n".join(metadata_block)


# --- Renderizador de Markdown Rico e Interativo (Qt RichText HTML) ---

def _compute_indent_level(leading_ws: str) -> int:
    """Calcula o nível de recuo suportando tabs (\t) e espaços."""
    if not leading_ws:
        return 0
    spaces = 0
    for ch in leading_ws:
        if ch == "\t":
            spaces += 4
        else:
            spaces += 1
    return spaces // 2 if spaces < 4 else spaces // 4


def _format_inline_markdown(text: str) -> str:
    """Formata elementos inline (links, anexos Joplin, código, negrito, itálico, tachado)."""
    if not text:
        return ""

    # 1. Escapa HTML básico
    escaped = html.escape(text, quote=False)

    # 2. Protege blocos de código inline `code`
    code_tokens = []
    def _save_code(m):
        idx = len(code_tokens)
        code_tokens.append(
            f'<code style="background-color:#EEF1F6; color:#C7254E; font-family:monospace;">&nbsp;{m.group(1)}&nbsp;</code>'
        )
        return f"@@INLINECODE_{idx}@@"

    escaped = re.sub(r"`([^`]+)`", _save_code, escaped)

    # 3. Imagens e anexos internos do Joplin: ![nome](:/id) ou [nome](:/id)
    link_tokens = []
    def _save_joplin_res(m):
        label = m.group(1).strip() or "Anexo"
        idx = len(link_tokens)
        link_tokens.append(
            f'<span style="color:#1B5EBF; background-color:#E8F0FE; font-size:small;">&nbsp;📎 {label}&nbsp;</span>'
        )
        return f"@@LINKTOKEN_{idx}@@"

    escaped = re.sub(r"!?\[([^\]]*)\]\(:/[a-fA-F0-9]+(?:\s+[^)]*)?\)", _save_joplin_res, escaped)

    # 4. Links Markdown padrão: [label](url)
    def _save_md_link(m):
        label = m.group(1)
        url = m.group(2).strip()
        idx = len(link_tokens)
        link_tokens.append(f'<a href="{url}" style="color:#1B5EBF; text-decoration:underline;">{label}</a>')
        return f"@@LINKTOKEN_{idx}@@"

    escaped = re.sub(r"!?\[([^\]]+)\]\((https?://[^)\s]+)\)", _save_md_link, escaped)

    # 5. URLs soltas no texto (ex: https://unesdoc.unesco.org/...)
    def _save_bare_url(m):
        url = m.group(1)
        idx = len(link_tokens)
        link_tokens.append(f'<a href="{url}" style="color:#1B5EBF; text-decoration:underline;">{url}</a>')
        return f"@@LINKTOKEN_{idx}@@"

    escaped = re.sub(r"(?<![\"'>])(https?://[^\s<)\]]+)", _save_bare_url, escaped)

    # 6. Negrito + Itálico, Negrito, Itálico e Tachado
    escaped = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"~~(.+?)~~", r"<s>\1</s>", escaped)

    # Restaura links e códigos inline
    for idx, token_html in enumerate(link_tokens):
        escaped = escaped.replace(f"@@LINKTOKEN_{idx}@@", token_html)
    for idx, token_html in enumerate(code_tokens):
        escaped = escaped.replace(f"@@INLINECODE_{idx}@@", token_html)

    return escaped


def render_markdown_to_html(body: str) -> str:
    """
    Converte o Markdown da nota em HTML rico otimizado para o QTextDocument do Qt Quick (Lomiri).
    Suporta:
    - Sublistas aninhadas com múltiplos Tabs (\t, \t\t, \t\t\t) sem virar bloco de código
    - Checklists interativos clicáveis (href="checkbox://LINE_INDEX")
    - Cabeçalhos H1..H4, citações, blocos de código, tabelas e links clicáveis
    """
    if not body or not body.strip():
        return '<p style="color:#888888;"><i>Nota vazia</i></p>'

    lines = body.splitlines()
    out = []
    in_code_block = False
    code_lines = []
    in_table = False
    table_rows = []

    checklist_re = re.compile(r"^(\s*)(?:[-*+]|\d+\.)\s+\[([ xX])\]\s*(.*)$")
    bullet_re = re.compile(r"^(\s*)[-*+]\s+(.*)$")
    ordered_re = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
    heading_re = re.compile(r"^\s*(#{1,6})\s+(.*)$")
    hr_re = re.compile(r"^\s*(?:[-*_]\s*){3,}$")

    def _flush_table():
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            in_table = False
            table_rows = []
            return
        t_html = ['<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse; margin-top:8px; margin-bottom:8px; border-color:#D0D7DE;">']
        for r_idx, row_cells in enumerate(table_rows):
            t_html.append("<tr>")
            for cell in row_cells:
                if r_idx == 0:
                    t_html.append(f'<th style="background-color:#F0F4F8; font-weight:bold;">{_format_inline_markdown(cell)}</th>')
                else:
                    t_html.append(f"<td>{_format_inline_markdown(cell)}</td>")
            t_html.append("</tr>")
        t_html.append("</table>")
        out.append("".join(t_html))
        in_table = False
        table_rows = []

    for idx, raw_line in enumerate(lines):
        # 1. Tratamento de blocos de código ```
        if raw_line.strip().startswith("```"):
            _flush_table()
            if not in_code_block:
                in_code_block = True
                code_lines = []
            else:
                in_code_block = False
                escaped_code = html.escape("\n".join(code_lines))
                out.append(
                    f'<pre style="background-color:#F4F6F9; color:#24292E; padding:10px; '
                    f'margin-top:8px; margin-bottom:8px; font-family:monospace; font-size:small;">{escaped_code}</pre>'
                )
            continue

        if in_code_block:
            code_lines.append(raw_line)
            continue

        # 2. Tratamento de tabelas Markdown | col1 | col2 |
        stripped = raw_line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 2:
            # Ignora linha separadora |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                in_table = True
                continue
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            in_table = True
            table_rows.append(cells)
            continue
        else:
            _flush_table()

        # 3. Linha em branco
        if not stripped:
            out.append('<p style="margin-top:2px; margin-bottom:2px;">&nbsp;</p>')
            continue

        # 4. Linha divisória horizontal (---, ***)
        if hr_re.match(raw_line):
            out.append('<hr style="border:0; height:1px; background-color:#D0D7DE; margin-top:10px; margin-bottom:10px;" />')
            continue

        # 5. Cabeçalhos (#, ##, ###, ####)
        m_head = heading_re.match(raw_line)
        if m_head:
            level = len(m_head.group(1))
            h_text = _format_inline_markdown(m_head.group(2).strip())
            if level == 1:
                out.append(
                    f'<p style="font-size:x-large; font-weight:bold; color:#1B5EBF; '
                    f'margin-top:10px; margin-bottom:6px;">{h_text}</p>'
                )
            elif level == 2:
                out.append(
                    f'<p style="font-size:large; font-weight:bold; color:#2C3E50; '
                    f'margin-top:10px; margin-bottom:4px;">{h_text}</p>'
                )
            elif level == 3:
                out.append(
                    f'<p style="font-size:medium; font-weight:bold; color:#34495E; '
                    f'margin-top:8px; margin-bottom:3px;">{h_text}</p>'
                )
            else:
                out.append(
                    f'<p style="font-size:medium; font-weight:bold; color:#5D6D7E; '
                    f'margin-top:6px; margin-bottom:2px;">{h_text}</p>'
                )
            continue

        # 6. Checklists interativos: - [ ] ou - [x] (em qualquer nível de recuo)
        m_chk = checklist_re.match(raw_line)
        if m_chk:
            indent_lvl = _compute_indent_level(m_chk.group(1))
            is_checked = m_chk.group(2).lower() == "x"
            item_text = _format_inline_markdown(m_chk.group(3))
            margin_px = indent_lvl * 22
            if is_checked:
                box_html = f'<a href="checkbox://{idx}" style="text-decoration:none; color:#0E8420; font-size:large;">☑</a>'
                text_html = f'<span style="color:#7F8C8D; text-decoration:line-through;">{item_text}</span>'
            else:
                box_html = f'<a href="checkbox://{idx}" style="text-decoration:none; color:#1B5EBF; font-size:large;">☐</a>'
                text_html = f'<span>{item_text}</span>'
            out.append(
                f'<p style="margin-left:{margin_px}px; margin-top:4px; margin-bottom:4px;">'
                f'{box_html}&nbsp;&nbsp;{text_html}</p>'
            )
            continue

        # 7. Listas com marcadores (-, *, +) com suporte a múltiplos níveis de Tab
        m_bul = bullet_re.match(raw_line)
        if m_bul:
            indent_lvl = _compute_indent_level(m_bul.group(1))
            item_text = _format_inline_markdown(m_bul.group(2))
            margin_px = indent_lvl * 22
            bullets = ["•", "◦", "▪", "▫"]
            b_char = bullets[min(indent_lvl, len(bullets) - 1)]
            b_color = "#1B5EBF" if indent_lvl == 0 else "#5D6D7E"
            out.append(
                f'<p style="margin-left:{margin_px}px; margin-top:3px; margin-bottom:3px;">'
                f'<span style="color:{b_color}; font-weight:bold;">{b_char}</span>&nbsp;&nbsp;{item_text}</p>'
            )
            continue

        # 8. Listas numeradas (1., 2., etc.) com suporte a múltiplos níveis de Tab
        m_ord = ordered_re.match(raw_line)
        if m_ord:
            indent_lvl = _compute_indent_level(m_ord.group(1))
            num_str = m_ord.group(2)
            item_text = _format_inline_markdown(m_ord.group(3))
            margin_px = indent_lvl * 22
            out.append(
                f'<p style="margin-left:{margin_px}px; margin-top:3px; margin-bottom:3px;">'
                f'<span style="color:#1B5EBF; font-weight:bold;">{num_str}.</span>&nbsp;&nbsp;{item_text}</p>'
            )
            continue

        # 9. Citações (> texto)
        if stripped.startswith(">"):
            q_text = _format_inline_markdown(stripped.lstrip(">").strip())
            out.append(
                f'<p style="margin-left:16px; color:#5D6D7E; font-style:italic; '
                f'margin-top:4px; margin-bottom:4px;">▎ {q_text}</p>'
            )
            continue

        # 10. Parágrafo normal
        out.append(
            f'<p style="margin-top:4px; margin-bottom:5px; line-height:135%;">{_format_inline_markdown(raw_line)}</p>'
        )

    _flush_table()
    if in_code_block and code_lines:
        escaped_code = html.escape("\n".join(code_lines))
        out.append(
            f'<pre style="background-color:#F4F6F9; color:#24292E; padding:10px; font-family:monospace;">{escaped_code}</pre>'
        )

    return "\n".join(out)


def toggle_markdown_checkbox(body: str, line_index: int) -> Tuple[str, bool]:
    """
    Alterna o estado [ ] <-> [x] na linha indicada do Markdown.
    Retorna (novo_body, alterou_bool).
    """
    if not body:
        return body, False
    lines = body.splitlines()
    if line_index < 0 or line_index >= len(lines):
        return body, False

    target = lines[line_index]
    checklist_re = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+\[)([ xX])(\]\s*.*)$")
    m = checklist_re.match(target)
    if not m:
        return body, False

    current_state = m.group(2)
    new_state = " " if current_state.lower() == "x" else "x"
    lines[line_index] = f"{m.group(1)}{new_state}{m.group(3)}"
    return "\n".join(lines), True
