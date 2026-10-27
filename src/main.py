"""
Ponto de Entrada da Ponte PyOtherSide (QML <-> Python) do Joplin UT
"""

from typing import List, Dict, Any, Optional

try:
    from config import load_settings, save_settings
    from db import (
        init_db,
        get_all_folders,
        get_folder_by_id,
        get_all_tags,
        get_tag_by_id,
        get_tag_by_title,
        upsert_tag,
        mark_tag_deleted,
        get_tags_for_note,
        toggle_note_tag_link,
        get_notes,
        get_note_by_id,
        upsert_note,
        upsert_folder,
        mark_note_deleted,
        mark_folder_deleted,
        format_display_date,
        get_connection
    )
    from joplin_parser import (
        generate_joplin_id,
        format_iso_time,
        render_markdown_to_html,
        toggle_markdown_checkbox
    )
    from webdav import WebDAVClient
    from sync import run_synchronization
except ImportError:
    from .config import load_settings, save_settings
    from .db import (
        init_db,
        get_all_folders,
        get_folder_by_id,
        get_all_tags,
        get_tag_by_id,
        get_tag_by_title,
        upsert_tag,
        mark_tag_deleted,
        get_tags_for_note,
        toggle_note_tag_link,
        get_notes,
        get_note_by_id,
        upsert_note,
        upsert_folder,
        mark_note_deleted,
        mark_folder_deleted,
        format_display_date,
        get_connection
    )
    from .joplin_parser import (
        generate_joplin_id,
        format_iso_time,
        render_markdown_to_html,
        toggle_markdown_checkbox
    )
    from .webdav import WebDAVClient
    from .sync import run_synchronization

# Inicializa o banco de dados na carga do módulo
try:
    init_db()
except Exception as e:
    print(f"[Main] Erro ao inicializar banco: {e}")

def init_app() -> str:
    """Chamado pelo QML no carregamento inicial da aplicação. Inicialização imediata sem travar a interface."""
    init_db()
    return "OK"

def get_folders_list() -> List[Dict[str, Any]]:
    """Retorna lista de cadernos hierarquizada (árvore com subpastas)."""
    try:
        return get_all_folders()
    except Exception as e:
        print(f"[Main] Erro ao obter cadernos: {e}")
        return []

def create_folder(title: str, parent_id: str = "") -> Dict[str, Any]:
    """Cria um novo caderno localmente e marca como dirty."""
    try:
        f_id = generate_joplin_id()
        now_str = format_iso_time()
        clean_title = title.strip()
        upsert_folder(
            folder_id=f_id,
            title=clean_title,
            parent_id=(parent_id or "").strip(),
            updated_time=now_str,
            dirty=1,
            deleted=0
        )
        return {"success": True, "id": f_id, "title": clean_title}
    except Exception as e:
        return {"success": False, "error": str(e)}

def rename_folder(folder_id: str, new_title: str) -> Dict[str, Any]:
    """Renomeia um caderno existente e marca como dirty para sincronização."""
    try:
        existing = get_folder_by_id(folder_id)
        if not existing:
            return {"success": False, "error": "Caderno não encontrado"}
        clean_title = new_title.strip()
        if not clean_title:
            return {"success": False, "error": "Nome inválido"}
        now_str = format_iso_time()
        upsert_folder(
            folder_id=folder_id,
            title=clean_title,
            parent_id=existing.get("parent_id") or "",
            updated_time=now_str,
            dirty=1,
            deleted=0
        )
        return {"success": True, "id": folder_id, "title": clean_title}
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_folder(folder_id: str) -> Dict[str, Any]:
    """Marca um caderno como deletado para remoção na próxima sincronização."""
    try:
        if not folder_id:
            return {"success": False, "error": "ID inválido"}
        mark_folder_deleted(folder_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Gestão de Etiquetas (Tags) ---

def get_tags_list() -> List[Dict[str, Any]]:
    """Retorna todas as tags ativas com a contagem de notas associadas."""
    try:
        return get_all_tags()
    except Exception as e:
        print(f"[Main] Erro ao listar tags: {e}", flush=True)
        return []

def create_tag(title: str, note_id: str = "") -> Dict[str, Any]:
    """Cria uma nova tag (ou reutiliza existente pelo nome) e opcionalmente a vincula a uma nota."""
    try:
        clean_title = (title or "").strip().lstrip("#").strip()
        if not clean_title:
            return {"success": False, "error": "Nome de tag vazio"}
        now_str = format_iso_time()
        existing = get_tag_by_title(clean_title)
        if existing:
            t_id = existing["id"]
            clean_title = existing["title"]
        else:
            t_id = generate_joplin_id()
            upsert_tag(tag_id=t_id, title=clean_title, updated_time=now_str, dirty=1, deleted=0)

        clean_note_id = (note_id or "").strip()
        if clean_note_id:
            current_note_tags = {t["id"] for t in get_tags_for_note(clean_note_id)}
            if t_id not in current_note_tags:
                toggle_note_tag_link(clean_note_id, t_id, generate_joplin_id(), now_str)

        return {
            "success": True,
            "id": t_id,
            "title": clean_title,
            "note_tags": get_tags_for_note(clean_note_id) if clean_note_id else []
        }
    except Exception as e:
        print(f"[Main] Erro ao criar tag: {e}", flush=True)
        return {"success": False, "error": str(e)}

def rename_tag(tag_id: str, new_title: str) -> Dict[str, Any]:
    """Renomeia uma tag existente e marca como dirty."""
    try:
        existing = get_tag_by_id(tag_id)
        if not existing:
            return {"success": False, "error": "Tag não encontrada"}
        clean_title = (new_title or "").strip().lstrip("#").strip()
        if not clean_title:
            return {"success": False, "error": "Nome inválido"}
        now_str = format_iso_time()
        upsert_tag(tag_id=tag_id, title=clean_title, updated_time=now_str, dirty=1, deleted=0)
        return {"success": True, "id": tag_id, "title": clean_title}
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_tag(tag_id: str) -> Dict[str, Any]:
    """Marca uma tag e todos os vínculos dela como deletados para sincronização."""
    try:
        if not tag_id:
            return {"success": False, "error": "ID inválido"}
        mark_tag_deleted(tag_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_note_tags(note_id: str) -> List[Dict[str, Any]]:
    """Retorna as tags associadas a uma nota específica."""
    try:
        return get_tags_for_note((note_id or "").strip())
    except Exception as e:
        return []

def toggle_note_tag(note_id: str, tag_id: str) -> Dict[str, Any]:
    """Alterna o vínculo entre uma nota e uma tag existente."""
    try:
        clean_note = (note_id or "").strip()
        clean_tag = (tag_id or "").strip()
        if not clean_note or not clean_tag:
            return {"success": False, "error": "Nota ou tag inválida"}
        now_str = format_iso_time()
        attached = toggle_note_tag_link(clean_note, clean_tag, generate_joplin_id(), now_str)
        return {
            "success": True,
            "attached": attached,
            "note_tags": get_tags_for_note(clean_note)
        }
    except Exception as e:
        print(f"[Main] Erro ao alternar tag na nota: {e}", flush=True)
        return {"success": False, "error": str(e)}

def get_notes_list(
    folder_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    include_subfolders: bool = False
) -> List[Dict[str, Any]]:
    """Retorna notas com preview para a lista principal respeitando a ordenação do Joplin."""
    try:
        s = load_settings()
        effective_sort_by = sort_by or s.get("sort_by", "updated_time")
        effective_sort_order = sort_order or s.get("sort_order", "DESC")
        target_folder = folder_id.strip() if folder_id and str(folder_id).strip() else None

        print(f"[Main] get_notes_list: folder_id='{target_folder}', sort='{effective_sort_by}' '{effective_sort_order}'", flush=True)

        return get_notes(
            folder_id=target_folder,
            search=search,
            sort_by=effective_sort_by,
            sort_order=effective_sort_order,
            include_subfolders=include_subfolders
        )
    except Exception as e:
        print(f"[Main] Erro ao listar notas: {e}", flush=True)
        return []

def save_sort_preferences(sort_by: str, sort_order: str) -> Dict[str, Any]:
    """Salva a preferência de ordenação do usuário."""
    print(f"[Main] save_sort_preferences: {sort_by} {sort_order}", flush=True)
    ok = save_settings({
        "sort_by": sort_by,
        "sort_order": sort_order
    })
    return {"success": ok}

def _resolve_folder_title(folder_id: str) -> str:
    if not folder_id:
        return "Sem Caderno"
    if folder_id.startswith("tag:"):
        return "Sem Caderno"
    folder = get_folder_by_id(folder_id)
    return folder.get("title", "Sem Caderno") if folder else "Sem Caderno"

def get_single_note(note_id: str) -> Optional[Dict[str, Any]]:
    """Retorna os dados completos de uma nota para o editor e o HTML pré-renderizado."""
    try:
        note = get_note_by_id(note_id)
        if not note:
            return None
        body_str = note.get("body") or ""
        note["rendered_html"] = render_markdown_to_html(body_str)
        note["updated_display"] = format_display_date(note.get("updated_time") or "")
        note["folder_title"] = _resolve_folder_title(note.get("parent_id") or "")
        note["tags"] = get_tags_for_note(note_id)
        return note
    except Exception as e:
        print(f"[Main] Erro ao obter nota {note_id}: {e}", flush=True)
        return None

def render_note_preview(body: str) -> str:
    """Converte o Markdown atual do editor em HTML rico para o modo de visualização."""
    try:
        return render_markdown_to_html(body or "")
    except Exception as e:
        print(f"[Main] Erro ao renderizar preview: {e}", flush=True)
        return ""

def save_note_content(note_id: str, parent_id: str, title: str, body: str) -> Dict[str, Any]:
    """Salva ou atualiza uma nota no banco local com flag dirty."""
    try:
        now_str = format_iso_time()
        is_new = not note_id or note_id.strip() == ""
        effective_id = note_id if not is_new else generate_joplin_id()
        
        # Se for nota existente, mantemos o created_time e atributos de todo originais
        created_time = now_str
        is_todo = 0
        todo_completed = 0
        if not is_new:
            existing = get_note_by_id(effective_id)
            if existing:
                if existing.get("created_time"):
                    created_time = existing["created_time"]
                is_todo = int(existing.get("is_todo") or 0)
                todo_completed = int(existing.get("todo_completed") or 0)

        clean_title = title.strip() if title and title.strip() else "Sem Título"
        clean_parent = (parent_id or "").strip()
        if clean_parent.startswith("tag:"):
            clean_parent = ""
        upsert_note(
            note_id=effective_id,
            parent_id=clean_parent,
            title=clean_title,
            body=body,
            created_time=created_time,
            updated_time=now_str,
            is_todo=is_todo,
            todo_completed=todo_completed,
            dirty=1,
            deleted=0
        )
        return {
            "success": True,
            "id": effective_id,
            "title": clean_title,
            "parent_id": clean_parent,
            "folder_title": _resolve_folder_title(clean_parent),
            "tags": get_tags_for_note(effective_id),
            "updated_display": format_display_date(now_str),
            "rendered_html": render_markdown_to_html(body or ""),
            "dirty": 1
        }
    except Exception as e:
        print(f"[Main] Erro ao salvar nota: {e}", flush=True)
        return {"success": False, "error": str(e)}

def move_note_to_folder(note_id: str, target_folder_id: str, title: str = "", body: str = "") -> Dict[str, Any]:
    """Move uma nota para outro caderno e salva com flag dirty = 1."""
    try:
        clean_folder = (target_folder_id or "").strip()
        if not note_id or not note_id.strip():
            return {
                "success": True,
                "parent_id": clean_folder,
                "folder_title": _resolve_folder_title(clean_folder)
            }
        existing = get_note_by_id(note_id)
        effective_title = title.strip() if title and title.strip() else (existing.get("title", "Sem Título") if existing else "Sem Título")
        effective_body = body if body != "" else (existing.get("body", "") if existing else "")
        return save_note_content(note_id, clean_folder, effective_title, effective_body)
    except Exception as e:
        print(f"[Main] Erro ao mover nota: {e}", flush=True)
        return {"success": False, "error": str(e)}

def toggle_note_checkbox(note_id: str, parent_id: str, title: str, body: str, line_index: int) -> Dict[str, Any]:
    """Alterna o checkbox [ ] <-> [x] na linha clicada da prévia e salva imediatamente como dirty."""
    try:
        new_body, changed = toggle_markdown_checkbox(body or "", int(line_index))
        if not changed:
            return {
                "success": False,
                "changed": False,
                "body": body,
                "rendered_html": render_markdown_to_html(body or "")
            }
        saved = save_note_content(note_id, parent_id, title, new_body)
        saved["changed"] = True
        saved["body"] = new_body
        return saved
    except Exception as e:
        print(f"[Main] Erro ao alternar checkbox: {e}", flush=True)
        return {"success": False, "changed": False, "error": str(e)}

def delete_single_note(note_id: str) -> Dict[str, Any]:
    """Marca nota como deletada para sincronização."""
    try:
        mark_note_deleted(note_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_app_settings() -> Dict[str, Any]:
    """Retorna as configurações atuais."""
    return load_settings()

def save_app_settings(server_url: str, username: str, password: str, joplin_dir: str) -> Dict[str, Any]:
    """Salva credenciais e configurações."""
    ok = save_settings({
        "server_url": server_url.strip(),
        "username": username.strip(),
        "password": password.strip(),
        "joplin_dir": joplin_dir.strip() or "Joplin"
    })
    return {"success": ok}

def test_nextcloud_connection(server_url: str, username: str, password: str, joplin_dir: str) -> Dict[str, Any]:
    """Verifica conexão com o Nextcloud."""
    client = WebDAVClient(server_url, username, password, joplin_dir or "Joplin")
    ok, msg = client.test_connection()
    return {"success": ok, "message": msg}

def perform_sync(force: bool = False) -> Dict[str, Any]:
    """Inicia a sincronização e retorna o resultado."""
    print("[Main] Iniciando sincronização WebDAV com o Nextcloud...", flush=True)
    result = run_synchronization(force_refresh=force)
    print(f"[Main] Resultado da sincronização: {result.get('message')}", flush=True)
    return result
