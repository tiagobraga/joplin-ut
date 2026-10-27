"""
Motor de Sincronização Bidirecional do Joplin UT
"""

from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional

try:
    from config import load_settings, save_settings
    from webdav import WebDAVClient
    from joplin_parser import (
        parse_joplin_file,
        serialize_joplin_note,
        serialize_joplin_folder,
        serialize_joplin_tag,
        serialize_joplin_note_tag,
        TYPE_NOTE,
        TYPE_FOLDER,
        TYPE_TAG,
        TYPE_NOTE_TAG
    )
    from db import (
        upsert_note,
        upsert_folder,
        upsert_tag,
        upsert_note_tag,
        get_local_etag_map,
        save_item_etag,
        get_dirty_items,
        clean_item_dirty,
        clean_table_dirty,
        purge_deleted_item,
        purge_table_deleted,
        mark_note_deleted
    )
except ImportError:
    from .config import load_settings, save_settings
    from .webdav import WebDAVClient
    from .joplin_parser import (
        parse_joplin_file,
        serialize_joplin_note,
        serialize_joplin_folder,
        serialize_joplin_tag,
        serialize_joplin_note_tag,
        TYPE_NOTE,
        TYPE_FOLDER,
        TYPE_TAG,
        TYPE_NOTE_TAG
    )
    from .db import (
        upsert_note,
        upsert_folder,
        upsert_tag,
        upsert_note_tag,
        get_local_etag_map,
        save_item_etag,
        get_dirty_items,
        clean_item_dirty,
        clean_table_dirty,
        purge_deleted_item,
        purge_table_deleted,
        mark_note_deleted
    )

def run_synchronization(progress_callback: Optional[Callable[[str, int], None]] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Executa o ciclo completo de sincronização bidirecional.
    """
    settings = load_settings()
    server_url = settings.get("server_url", "").strip()
    username = settings.get("username", "").strip()
    password = settings.get("password", "").strip()
    joplin_folder = settings.get("joplin_dir", "Joplin").strip()

    if not server_url or not username or not password:
        return {
            "success": False,
            "message": "Configurações incompletas. Informe URL, usuário e senha do Nextcloud."
        }

    client = WebDAVClient(server_url, username, password, joplin_folder)

    # 1. Testar conexão
    if progress_callback:
        progress_callback("Conectando ao Nextcloud...", 10)
    
    ok, msg = client.test_connection()
    if not ok:
        return {"success": False, "message": msg}

    stats = {
        "downloaded_notes": 0,
        "downloaded_folders": 0,
        "downloaded_tags": 0,
        "uploaded_notes": 0,
        "uploaded_folders": 0,
        "uploaded_tags": 0,
        "deleted_remote": 0,
        "errors": []
    }

    try:
        # 2. PROPFIND remoto
        if progress_callback:
            progress_callback("Listando arquivos remotos...", 25)
        
        remote_files = client.list_files()
        local_etags = {} if force_refresh else get_local_etag_map()
        initial_dirty = get_dirty_items()
        dirty_ids = (
            {x["id"] for x in initial_dirty["notes"]}
            | {x["id"] for x in initial_dirty["folders"]}
            | {x["id"] for x in initial_dirty.get("tags", [])}
            | {x["id"] for x in initial_dirty.get("note_tags", [])}
        )

        # Filtrar apenas arquivos .md (exclui .resource, .sync, etc)
        joplin_md_files = [f for f in remote_files if f["filename"].endswith(".md") and not f["is_dir"]]

        # 3. Ciclo de DOWNLOAD (PULL)
        total_remote = len(joplin_md_files)
        if progress_callback:
            progress_callback(f"Processando {total_remote} itens remotos...", 40)

        for idx, item in enumerate(joplin_md_files):
            filename = item["filename"]
            item_id = filename[:-3]  # remove '.md'
            remote_etag = item["etag"]

            # Nunca sobrescreve itens modificados localmente que ainda serão enviados no PUSH
            if item_id in dirty_ids:
                continue

            # Se o etag local for igual ao remoto e não for recarga forçada, pula
            if not force_refresh and local_etags.get(item_id) == remote_etag and remote_etag != "":
                continue

            try:
                content, etag = client.get_file_content(filename)
                effective_etag = etag or remote_etag
                parsed = parse_joplin_file(content)
                meta = parsed.get("metadata", {})
                item_type = meta.get("type_", TYPE_NOTE)

                if item_type == TYPE_FOLDER:
                    u_time = meta.get("user_updated_time") or meta.get("updated_time") or ""
                    upsert_folder(
                        folder_id=meta.get("id", item_id),
                        title=parsed.get("title", "Sem Nome"),
                        parent_id=meta.get("parent_id", ""),
                        updated_time=u_time,
                        dirty=0,
                        deleted=0
                    )
                    save_item_etag(item_id, effective_etag, item_type)
                    stats["downloaded_folders"] += 1
                elif item_type == TYPE_NOTE:
                    c_time = meta.get("user_created_time") or meta.get("created_time") or ""
                    u_time = meta.get("user_updated_time") or meta.get("updated_time") or c_time or ""
                    upsert_note(
                        note_id=meta.get("id", item_id),
                        parent_id=meta.get("parent_id", ""),
                        title=parsed.get("title", "Sem Título"),
                        body=parsed.get("body", ""),
                        created_time=c_time,
                        updated_time=u_time,
                        is_todo=meta.get("is_todo", 0),
                        todo_completed=meta.get("todo_completed", 0),
                        dirty=0,
                        deleted=0,
                        etag=effective_etag
                    )
                    save_item_etag(item_id, effective_etag, item_type)
                    stats["downloaded_notes"] += 1
                elif item_type == TYPE_TAG:
                    u_time = meta.get("user_updated_time") or meta.get("updated_time") or ""
                    upsert_tag(
                        tag_id=meta.get("id", item_id),
                        title=parsed.get("title", "Sem Nome"),
                        updated_time=u_time,
                        dirty=0,
                        deleted=0
                    )
                    save_item_etag(item_id, effective_etag, item_type)
                    stats["downloaded_tags"] += 1
                elif item_type == TYPE_NOTE_TAG:
                    u_time = meta.get("user_updated_time") or meta.get("updated_time") or ""
                    n_id = meta.get("note_id", "")
                    t_id = meta.get("tag_id", "")
                    if n_id and t_id:
                        upsert_note_tag(
                            assoc_id=meta.get("id", item_id),
                            note_id=n_id,
                            tag_id=t_id,
                            updated_time=u_time,
                            dirty=0,
                            deleted=0
                        )
                    save_item_etag(item_id, effective_etag, item_type)
                else:
                    # Registra o ETag de outros tipos do Joplin (resources, revisions)
                    # para não re-baixá-los a cada sincronização
                    save_item_etag(item_id, effective_etag, item_type)
            except Exception as e:
                stats["errors"].append(f"Erro ao baixar {filename}: {str(e)}")

        # 4. Ciclo de ENVIO (PUSH)
        if progress_callback:
            progress_callback("Enviando alterações locais...", 75)

        dirty = get_dirty_items()

        # Envia pastas criadas ou editadas
        for folder in dirty["folders"]:
            f_id = folder["id"]
            if folder["deleted"] == 1:
                try:
                    client.delete_file(f"{f_id}.md")
                    purge_deleted_item(f_id, is_note=False)
                    stats["deleted_remote"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao deletar pasta {f_id}: {str(e)}")
            else:
                try:
                    content = serialize_joplin_folder(
                        folder_id=f_id,
                        title=folder["title"],
                        parent_id=folder.get("parent_id", ""),
                        updated_time=folder.get("updated_time", "")
                    )
                    new_etag = client.put_file_content(f"{f_id}.md", content)
                    clean_item_dirty(f_id, is_note=False)
                    if new_etag:
                        save_item_etag(f_id, new_etag, TYPE_FOLDER)
                    stats["uploaded_folders"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao enviar pasta {f_id}: {str(e)}")

        # Envia notas criadas ou editadas
        for note in dirty["notes"]:
            n_id = note["id"]
            if note["deleted"] == 1:
                try:
                    client.delete_file(f"{n_id}.md")
                    purge_deleted_item(n_id, is_note=True)
                    stats["deleted_remote"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao deletar nota {n_id}: {str(e)}")
            else:
                try:
                    content = serialize_joplin_note(
                        note_id=n_id,
                        parent_id=note.get("parent_id", ""),
                        title=note["title"],
                        body=note.get("body", ""),
                        created_time=note.get("created_time", ""),
                        updated_time=note.get("updated_time", ""),
                        is_todo=note.get("is_todo", 0),
                        todo_completed=note.get("todo_completed", 0)
                    )
                    new_etag = client.put_file_content(f"{n_id}.md", content)
                    clean_item_dirty(n_id, is_note=True, new_etag=new_etag)
                    if new_etag:
                        save_item_etag(n_id, new_etag, TYPE_NOTE)
                    stats["uploaded_notes"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao enviar nota {n_id}: {str(e)}")

        # Envia tags criadas ou editadas
        for tag in dirty.get("tags", []):
            t_id = tag["id"]
            if tag["deleted"] == 1:
                try:
                    client.delete_file(f"{t_id}.md")
                    purge_table_deleted("tags", t_id)
                    stats["deleted_remote"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao deletar tag {t_id}: {str(e)}")
            else:
                try:
                    content = serialize_joplin_tag(
                        tag_id=t_id,
                        title=tag["title"],
                        updated_time=tag.get("updated_time", "")
                    )
                    new_etag = client.put_file_content(f"{t_id}.md", content)
                    clean_table_dirty("tags", t_id)
                    if new_etag:
                        save_item_etag(t_id, new_etag, TYPE_TAG)
                    stats["uploaded_tags"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao enviar tag {t_id}: {str(e)}")

        # Envia associações nota-tag (note_tags) criadas ou removidas
        for nt in dirty.get("note_tags", []):
            nt_id = nt["id"]
            if nt["deleted"] == 1:
                try:
                    client.delete_file(f"{nt_id}.md")
                    purge_table_deleted("note_tags", nt_id)
                    stats["deleted_remote"] += 1
                except Exception as e:
                    stats["errors"].append(f"Erro ao deletar vínculo tag {nt_id}: {str(e)}")
            else:
                try:
                    content = serialize_joplin_note_tag(
                        assoc_id=nt_id,
                        note_id=nt["note_id"],
                        tag_id=nt["tag_id"],
                        updated_time=nt.get("updated_time", "")
                    )
                    new_etag = client.put_file_content(f"{nt_id}.md", content)
                    clean_table_dirty("note_tags", nt_id)
                    if new_etag:
                        save_item_etag(nt_id, new_etag, TYPE_NOTE_TAG)
                except Exception as e:
                    stats["errors"].append(f"Erro ao enviar vínculo tag {nt_id}: {str(e)}")

        # Salva data e hora local da sincronização
        now_iso = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        save_settings({"last_sync": now_iso})

        if progress_callback:
            progress_callback("Sincronização concluída com sucesso!", 100)

        return {
            "success": True,
            "stats": stats,
            "last_sync": now_iso,
            "message": (
                f"Sincronização concluída! "
                f"Baixadas: {stats['downloaded_notes']} notas, {stats['downloaded_folders']} cadernos. "
                f"Enviadas: {stats['uploaded_notes']} notas, {stats['uploaded_folders']} cadernos."
            )
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Erro durante a sincronização: {str(e)}"
        }
