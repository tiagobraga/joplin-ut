"""
Gerenciamento do Banco de Dados SQLite Local do Joplin UT
"""

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    from config import get_data_dir
except ImportError:
    from .config import get_data_dir

def get_db_path() -> str:
    return str(get_data_dir() / "joplin_local.db")

@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Cria as tabelas necessárias e índices para alta performance de busca."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela de pastas / cadernos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                parent_id TEXT,
                updated_time TEXT,
                dirty INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0
            )
        """)

        # Tabela de notas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                title TEXT NOT NULL,
                body TEXT,
                created_time TEXT,
                updated_time TEXT,
                is_todo INTEGER DEFAULT 0,
                todo_completed INTEGER DEFAULT 0,
                dirty INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0,
                etag TEXT,
                FOREIGN KEY(parent_id) REFERENCES folders(id) ON DELETE SET NULL
            )
        """)

        # Tabela de estado e metadados de sincronização
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Cache de ETags para todos os itens remotos (.md de pastas, tags, revisões, recursos, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etag_cache (
                id TEXT PRIMARY KEY,
                etag TEXT NOT NULL,
                item_type INTEGER DEFAULT 0
            )
        """)

        # Tabela de etiquetas (Tags - type_: 5)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                updated_time TEXT,
                dirty INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0
            )
        """)

        # Tabela de associação Nota <-> Tag (NoteTag - type_: 6)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_tags (
                id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                updated_time TEXT,
                dirty INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0
            )
        """)

        # Índices para pesquisa instantânea e filtros
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_parent ON notes(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title COLLATE NOCASE ASC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_dirty ON notes(dirty)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_dirty ON folders(dirty)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_dirty ON tags(dirty)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_note ON note_tags(note_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_dirty ON note_tags(dirty)")

        conn.commit()

# --- Auxiliares de Formatação ---

def clean_markdown_preview(raw_text: str) -> str:
    """Remove caracteres especiais de markdown do preview para ficar limpo como no app móvel."""
    if not raw_text:
        return ""
    # Remove cabeçalhos #
    t = re.sub(r"^#+\s*", "", raw_text, flags=re.MULTILINE)
    # Remove formatações de negrito e itálico
    t = re.sub(r"[*_]{1,3}", "", t)
    # Remove marcadores de lista
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.MULTILINE)
    # Remove links markdown [label](url) -> label
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    # Junta em linha única
    t = " ".join(t.split())
    return t[:130]

def format_display_date(date_str: str) -> str:
    """Converte ISO timestamp do Joplin para formato legível (ex: 26/10/2026 ou 18:30)."""
    if not date_str:
        return ""
    try:
        # Formatos comuns: '2026-04-25T11:36:56.909Z' ou milissegundos
        if date_str.isdigit():
            dt = datetime.fromtimestamp(int(date_str) / 1000.0, tz=timezone.utc)
        else:
            clean_iso = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_iso)
        
        now = datetime.now(timezone.utc)
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        elif dt.year == now.year:
            return dt.strftime("%d/%m")
        else:
            return dt.strftime("%d/%m/%y")
    except Exception:
        # Fallback para os 10 primeiros caracteres se for YYYY-MM-DD
        return date_str[:10] if len(date_str) >= 10 else date_str

# --- Operações de Cadernos (Hierarquia de Árvore) ---

def get_descendant_folder_ids(folder_id: str) -> List[str]:
    """Retorna o ID da pasta e todos os IDs de pastas filhas/netas recursivamente."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, parent_id FROM folders WHERE deleted = 0")
        all_f = [dict(r) for r in cursor.fetchall()]

    by_parent: Dict[str, List[str]] = {}
    for f in all_f:
        p = f.get("parent_id") or ""
        by_parent.setdefault(p, []).append(f["id"])

    result = [folder_id]
    queue = [folder_id]
    while queue:
        curr = queue.pop(0)
        children = by_parent.get(curr, [])
        for ch in children:
            if ch not in result:
                result.append(ch)
                queue.append(ch)
    return result

def get_all_folders() -> List[Dict[str, Any]]:
    """
    Retorna todos os cadernos ativos estruturados em árvore hierárquica.
    Cada item inclui 'level', 'has_children' e 'display_title'.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.title, COALESCE(f.parent_id, '') as parent_id, f.updated_time,
                   COUNT(n.id) as notes_count
            FROM folders f
            LEFT JOIN notes n ON n.parent_id = f.id AND n.deleted = 0
            WHERE f.deleted = 0
            GROUP BY f.id, f.title, f.parent_id, f.updated_time
            ORDER BY f.title COLLATE NOCASE ASC
        """)
        raw_folders = [dict(row) for row in cursor.fetchall()]

    # Mapeia pastas filhas por pai
    by_parent: Dict[str, List[Dict[str, Any]]] = {}
    for f in raw_folders:
        p = f.get("parent_id") or ""
        by_parent.setdefault(p, []).append(f)

    ordered: List[Dict[str, Any]] = []

    def add_subtree(parent_id: str, level: int):
        children = by_parent.get(parent_id, [])
        for ch in children:
            item = ch.copy()
            item["level"] = level
            has_sub = len(by_parent.get(ch["id"], [])) > 0
            item["has_children"] = has_sub
            prefix = "  ↳ " if level > 0 else ""
            item["display_title"] = f"{prefix}{ch['title']}"
            ordered.append(item)
            add_subtree(ch["id"], level + 1)

    # Constrói a partir da raiz (parent_id == "")
    add_subtree("", 0)

    # Pastas órfãs cujo pai não foi localizado
    found_ids = {x["id"] for x in ordered}
    for f in raw_folders:
        if f["id"] not in found_ids:
            f_copy = f.copy()
            f_copy["level"] = 0
            f_copy["has_children"] = False
            f_copy["display_title"] = f["title"]
            ordered.append(f_copy)

    return ordered

def get_folder_by_id(folder_id: str) -> Optional[Dict[str, Any]]:
    if not folder_id:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE id = ? AND deleted = 0", (folder_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def upsert_folder(folder_id: str, title: str, parent_id: str = "", updated_time: str = "", dirty: int = 0, deleted: int = 0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO folders (id, title, parent_id, updated_time, dirty, deleted)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                parent_id = excluded.parent_id,
                updated_time = excluded.updated_time,
                dirty = excluded.dirty,
                deleted = excluded.deleted
        """, (folder_id, title, parent_id, updated_time, dirty, deleted))
        conn.commit()

def mark_folder_deleted(folder_id: str):
    """Marca um caderno como deletado para remoção no Nextcloud na próxima sincronização."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE folders SET deleted = 1, dirty = 1 WHERE id = ?", (folder_id,))
        conn.commit()

# --- Operações de Etiquetas (Tags & NoteTags) ---

def get_all_tags() -> List[Dict[str, Any]]:
    """Retorna todas as tags ativas em ordem alfabética com contagem de notas associadas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.title, t.updated_time, t.dirty,
                   COUNT(DISTINCT n.id) as notes_count
            FROM tags t
            LEFT JOIN note_tags nt ON nt.tag_id = t.id AND nt.deleted = 0
            LEFT JOIN notes n ON n.id = nt.note_id AND n.deleted = 0
            WHERE t.deleted = 0
            GROUP BY t.id, t.title, t.updated_time, t.dirty
            ORDER BY t.title COLLATE NOCASE ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

def get_tag_by_id(tag_id: str) -> Optional[Dict[str, Any]]:
    if not tag_id:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tags WHERE id = ? AND deleted = 0", (tag_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_tag_by_title(title: str) -> Optional[Dict[str, Any]]:
    if not title or not title.strip():
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tags WHERE LOWER(title) = LOWER(?) AND deleted = 0", (title.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def upsert_tag(tag_id: str, title: str, updated_time: str = "", dirty: int = 0, deleted: int = 0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tags (id, title, updated_time, dirty, deleted)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                updated_time = excluded.updated_time,
                dirty = excluded.dirty,
                deleted = excluded.deleted
        """, (tag_id, title.strip(), updated_time, dirty, deleted))
        conn.commit()

def mark_tag_deleted(tag_id: str):
    """Marca a tag e todos os vínculos note_tags dela como deletados para sincronização."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tags SET deleted = 1, dirty = 1 WHERE id = ?", (tag_id,))
        cursor.execute("UPDATE note_tags SET deleted = 1, dirty = 1 WHERE tag_id = ? AND deleted = 0", (tag_id,))
        conn.commit()

def upsert_note_tag(assoc_id: str, note_id: str, tag_id: str, updated_time: str = "", dirty: int = 0, deleted: int = 0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO note_tags (id, note_id, tag_id, updated_time, dirty, deleted)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                note_id = excluded.note_id,
                tag_id = excluded.tag_id,
                updated_time = excluded.updated_time,
                dirty = excluded.dirty,
                deleted = excluded.deleted
        """, (assoc_id, note_id, tag_id, updated_time, dirty, deleted))
        conn.commit()

def get_tags_for_note(note_id: str) -> List[Dict[str, Any]]:
    """Retorna todas as tags ativas associadas a uma nota."""
    if not note_id:
        return []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.title
            FROM tags t
            INNER JOIN note_tags nt ON nt.tag_id = t.id
            WHERE nt.note_id = ? AND nt.deleted = 0 AND t.deleted = 0
            ORDER BY t.title COLLATE NOCASE ASC
        """, (note_id,))
        return [dict(r) for r in cursor.fetchall()]

def toggle_note_tag_link(note_id: str, tag_id: str, new_assoc_id: str, now_str: str) -> bool:
    """Alterna o vínculo entre uma nota e uma tag. Retorna True se ficou vinculada, False se desvinculada."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, deleted FROM note_tags WHERE note_id = ? AND tag_id = ? ORDER BY deleted ASC LIMIT 1",
            (note_id, tag_id)
        )
        row = cursor.fetchone()
        if row and row["deleted"] == 0:
            cursor.execute(
                "UPDATE note_tags SET deleted = 1, dirty = 1, updated_time = ? WHERE note_id = ? AND tag_id = ? AND deleted = 0",
                (now_str, note_id, tag_id)
            )
            conn.commit()
            return False
        elif row and row["deleted"] == 1:
            cursor.execute(
                "UPDATE note_tags SET deleted = 0, dirty = 1, updated_time = ? WHERE id = ?",
                (now_str, row["id"])
            )
            conn.commit()
            return True
        else:
            cursor.execute(
                "INSERT INTO note_tags (id, note_id, tag_id, updated_time, dirty, deleted) VALUES (?, ?, ?, ?, 1, 0)",
                (new_assoc_id, note_id, tag_id, now_str)
            )
            conn.commit()
            return True

# --- Operações de Notas (Notes) com Ordenação Avançada ---

VALID_SORT_FIELDS = {
    "updated_time": "updated_time",
    "created_time": "created_time",
    "title": "title COLLATE NOCASE"
}

def get_notes(
    folder_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "updated_time",
    sort_order: str = "DESC",
    include_subfolders: bool = False
) -> List[Dict[str, Any]]:
    """
    Retorna lista de notas com ordenação customizável (data de atualização, criação, título),
    suporte a filtro por caderno específico, filtro por tag ('tag:<id>') e busca por texto.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        params = []
        conditions = ["deleted = 0"]

        if folder_id and folder_id.strip():
            target_id = folder_id.strip()
            if target_id.startswith("tag:"):
                tag_id = target_id[4:].strip()
                conditions.append("id IN (SELECT note_id FROM note_tags WHERE tag_id = ? AND deleted = 0)")
                params.append(tag_id)
            elif include_subfolders:
                folder_ids = get_descendant_folder_ids(target_id)
                placeholders = ",".join(["?"] * len(folder_ids))
                conditions.append(f"parent_id IN ({placeholders})")
                params.extend(folder_ids)
            else:
                conditions.append("parent_id = ?")
                params.append(target_id)

        if search and search.strip():
            query_term = f"%{search.strip()}%"
            conditions.append("(title LIKE ? OR body LIKE ?)")
            params.extend([query_term, query_term])

        where_clause = " WHERE " + " AND ".join(conditions)

        # Validação do campo de ordenação
        sort_col = VALID_SORT_FIELDS.get(sort_by, "updated_time")
        order_dir = "ASC" if str(sort_order).upper() == "ASC" else "DESC"

        sql = f"""
            SELECT id, parent_id, title, body,
                   created_time, updated_time, is_todo, todo_completed, dirty
            FROM notes
            {where_clause}
            ORDER BY {sort_col} {order_dir}
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        result = []
        for r in rows:
            d = dict(r)
            d["preview"] = clean_markdown_preview(d.get("body", ""))
            # Formata a data para exibição destacada no card
            date_to_format = d.get("updated_time") if sort_by != "created_time" else d.get("created_time")
            d["date_display"] = format_display_date(date_to_format or d.get("updated_time") or "")
            d.pop("body", None)
            result.append(d)
        return result

def get_note_by_id(note_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def upsert_note(
    note_id: str,
    parent_id: str,
    title: str,
    body: str,
    created_time: str,
    updated_time: str,
    is_todo: int = 0,
    todo_completed: int = 0,
    dirty: int = 0,
    deleted: int = 0,
    etag: str = ""
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notes (id, parent_id, title, body, created_time, updated_time, is_todo, todo_completed, dirty, deleted, etag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                parent_id = excluded.parent_id,
                title = excluded.title,
                body = excluded.body,
                created_time = excluded.created_time,
                updated_time = excluded.updated_time,
                is_todo = excluded.is_todo,
                todo_completed = excluded.todo_completed,
                dirty = excluded.dirty,
                deleted = excluded.deleted,
                etag = CASE WHEN excluded.etag != '' THEN excluded.etag ELSE notes.etag END
        """, (note_id, parent_id, title, body, created_time, updated_time, is_todo, todo_completed, dirty, deleted, etag))
        conn.commit()

def mark_note_deleted(note_id: str):
    """Marca uma nota e seus vínculos de tag como deletados para envio na próxima sincronização."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notes SET deleted = 1, dirty = 1 WHERE id = ?", (note_id,))
        cursor.execute("UPDATE note_tags SET deleted = 1, dirty = 1 WHERE note_id = ? AND deleted = 0", (note_id,))
        conn.commit()

def get_dirty_items() -> Dict[str, List[Dict[str, Any]]]:
    """Retorna itens que precisam ser enviados ao Nextcloud."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE dirty = 1")
        dirty_notes = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM folders WHERE dirty = 1")
        dirty_folders = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM tags WHERE dirty = 1")
        dirty_tags = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM note_tags WHERE dirty = 1")
        dirty_note_tags = [dict(row) for row in cursor.fetchall()]

        return {
            "notes": dirty_notes,
            "folders": dirty_folders,
            "tags": dirty_tags,
            "note_tags": dirty_note_tags
        }

def clean_item_dirty(item_id: str, is_note: bool, new_etag: str = ""):
    table = "notes" if is_note else "folders"
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_note and new_etag:
            cursor.execute(f"UPDATE {table} SET dirty = 0, etag = ? WHERE id = ?", (new_etag, item_id))
        else:
            cursor.execute(f"UPDATE {table} SET dirty = 0 WHERE id = ?", (item_id,))
        conn.commit()

def clean_table_dirty(table: str, item_id: str):
    if table not in ("notes", "folders", "tags", "note_tags"):
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {table} SET dirty = 0 WHERE id = ?", (item_id,))
        conn.commit()

def purge_deleted_item(item_id: str, is_note: bool):
    table = "notes" if is_note else "folders"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        cursor.execute("DELETE FROM etag_cache WHERE id = ?", (item_id,))
        conn.commit()

def purge_table_deleted(table: str, item_id: str):
    if table not in ("notes", "folders", "tags", "note_tags"):
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        cursor.execute("DELETE FROM etag_cache WHERE id = ?", (item_id,))
        conn.commit()

def save_item_etag(item_id: str, etag: str, item_type: int = 0):
    """Salva o ETag de qualquer arquivo .md do Joplin para evitar downloads repetidos."""
    if not item_id or not etag:
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO etag_cache (id, etag, item_type)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                etag = excluded.etag,
                item_type = excluded.item_type
        """, (item_id, etag, int(item_type or 0)))
        conn.commit()

def get_local_etag_map() -> Dict[str, str]:
    """Retorna mapa de {id: etag} de todos os itens locais (notas, cadernos, tags, revisões)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, etag FROM etag_cache WHERE etag IS NOT NULL AND etag != ''")
        etag_map = {row["id"]: row["etag"] for row in cursor.fetchall()}
        cursor.execute("SELECT id, etag FROM notes WHERE etag IS NOT NULL AND etag != ''")
        for row in cursor.fetchall():
            etag_map[row["id"]] = row["etag"]
        return etag_map
