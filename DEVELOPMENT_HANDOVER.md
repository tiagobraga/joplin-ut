# Relatório Técnico e Documentação de Continuidade (Handover)

**Projeto**: Joplin UT (Ubuntu Touch Client)  
**Versão Atual no Aparelho**: `1.2.2`  
**Dispositivo Alvo Homologado**: Xiaomi Poco X3 NFC (`surya` - arquitetura `arm64`), Ubuntu Touch 24.04-2.x (Noble Numbat)  
**Framework Click**: `ubuntu-touch-24.04-1.x` | **Política AppArmor**: `2404.1`  
**Data da Documentação**: 27/10/2026  

---

## 1. Resumo do Status Atual do Projeto

Todas as **5 fases** planejadas do projeto foram concluídas, testadas e homologadas no dispositivo real e com o servidor Nextcloud + Joplin Desktop:

| Fase | Descrição | Status | Detalhes |
|---|---|---|---|
| **Fase 1** | Fundação do Projeto, Clickable, Shell QML e Empacotamento | **Concluída** | Build CMake, manifest, ícone vetorial SVG, AppArmor 2404.1. |
| **Fase 2** | Backend WebDAV, Parser Joplin, Banco SQLite e Pull Sync | **Concluída** | **231+ notas e 24 cadernos** sincronizados via WebDAV com cache de ETags (`etag_cache`). |
| **Fase 3** | Navegação Lomiri, Árvore de Cadernos e Ordenação | **Concluída** | Gaveta hierárquica expansível/recolhível (`visibleFoldersModel`), ordenação instantânea com cache JS (`cachedNotes`). |
| **Fase 4** | Visualização Rica (Markdown), Edição e Push Sync | **Concluída** | Visualização RichText, checklists interativos `[ ]`/`[x]`, botões de recuo (`⇤`/`⇥`), auto-continuação de listas ao dar Enter e Push Sync WebDAV (`PUT`/`DELETE`/`UNLOCK`). |
| **Fase 5** | Validação OpenStore, Revisão de Políticas e Publicação | **Concluída** | Pacote `joplin-ut.braga_1.2.2_all.click` validado (permissões `0644`/`0755`, AppArmor `2404.1`), ícone `512x512` e screenshots verticais em `store/`. |

---

## 2. Decisões Arquiteturais e Armadilhas Cruciais Resolvidas

### 2.1. Reatividade de Listas e Ponteiros C++ no Qt Quick (`ListModel` vs `Array JS`)
- **Problema encontrado**: Chamar `notesListModel.get(i)` e em seguida `notesListModel.clear()` invalida os ponteiros `QQmlDMListAccessorData` do Qt Quick 2.12, fazendo as notas aparecerem como `"Sem Título"`.
- **Solução implementada (`NotesListPage.qml`)**: Mantemos um array JS puro (`cachedNotes`) clonado com `cloneNoteItem()` e reconstruímos o `ListModel` via `rebuildListModel()` a partir dos dados primitivos.
- **Gaveta de Cadernos (`NotebookDrawer.qml`)**: Utiliza um `ListModel` nativo (`visibleFoldersModel`) reconstruído por `rebuildVisibleFolders()`, com `MouseArea` separadas lado a lado para a seta de expandir/recolher (`expandMouseArea`) e para a seleção do caderno (`rowMouseArea`).

### 2.2. Ponte PyOtherSide (Chamadas Assíncronas Obrigam Callback)
- **Regra**: **Toda e qualquer chamada ao PyOtherSide no QML deve sempre conter os 3 parâmetros:**
  ```javascript
  py.call('main.nome_da_funcao', [arg1, arg2], function(resultado) {
      // callback obrigatório
  });
  ```
- Nunca passe valores `undefined` em listas de argumentos para o PyOtherSide; use sempre fallback para string vazia: `(param || "")`.

### 2.3. Cache Global de ETags (`etag_cache`) e Fechamento de Conexões SQLite
- A pasta do Joplin no Nextcloud armazena não apenas notas e pastas, mas centenas de arquivos `.md` de tags, recursos (`type_: 4, 5, 6`) e revisões (`type_: 13`).
- A tabela `etag_cache` em `src/db.py` armazena o ETag de **todos** os arquivos `.md` remotos (`1.103` itens), reduzindo o tempo de sincronização incremental de ~11 minutos para **~2–3 segundos**.
- `get_connection()` em `src/db.py` utiliza `@contextmanager` garantindo `conn.close()` após cada operação.

### 2.4. Editor Markdown, Checklists e Auto-Continuação (`NoteEditPage.qml` & `joplin_parser.py`)
- Notas existentes abrem em **Modo de Visualização Rica** (`isPreviewMode: !isNewNote`), permitindo tocar diretamente nos checkboxes (`☐` / `☑`) para alternar seu estado (`checkbox://LINE_INDEX`), salvando imediatamente no SQLite (`dirty = 1`) e preservando a posição de rolagem (`contentY`).
- No **Modo de Edição**:
  - Botões **`⇤`** (`outdentCurrentLine`) e **`⇥`** (`indentCurrentLine`) adicionam/removem tabulações (`\t`) no início da linha.
  - Pressionar **Enter** (`handleBodyEnterContinuation`) continua automaticamente listas (`- `, `* `, `+ `, `1. `) e checkboxes (`- [ ] `) mantendo a indentação da linha anterior; pressionar **Enter** novamente em um marcador vazio encerra a lista.

### 2.5. Tratamento de Bloqueios WebDAV do Editor Web do Nextcloud (`423 Locked` e `type\_: 1`)
- Se um arquivo `.md` for aberto pelo aplicativo web **Text** do Nextcloud, o Nextcloud aplica um `files_lock` (`423 Locked`) e escapa `type_: 1` para `type\_: 1`.
- `src/webdav.py` possui `unlock_file()` automático (`UNLOCK` com `X-User-Lock: 1`) quando recebe `HTTP 423`, e `src/joplin_parser.py` normaliza `\_` nos metadados de rodapé.

---

## 3. Artefatos Prontos para Publicação na OpenStore (`store/`)

Todos os arquivos necessários para submissão em [open-store.io](https://open-store.io/) estão organizados na pasta `store/`:
- **Pacote Click**: `store/joplin-ut.braga_1.2.2_all.click` (permissões `0644`/`0755`, arquitetura `all`, framework `ubuntu-touch-24.04-1.x`, AppArmor `2404.1`).
- **Ícone 512x512 PNG**: `store/logo-512.png` (e vetorial em `assets/logo.svg`).
- **Screenshots Verticais (1080x2160)**:
  - `store/screenshots/01-notes-list.png`
  - `store/screenshots/02-notebook-drawer.png`
  - `store/screenshots/03-note-preview-edit.png`
