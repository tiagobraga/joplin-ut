# Guia de Release e Changelog – Joplin UT v1.5.0

Este documento reúne todas as informações necessárias para submissão da versão **1.5.0** do **Joplin UT** (`joplin-ut.braga`) na **OpenStore** ([open-store.io](https://open-store.io)).

---

## 📦 Arquivo do Pacote Click para Submissão

O pacote `.click` compilado e validado encontra-se no seguinte caminho absoluto:

```bash
/home/braga/Nextcloud/Projetos/2026_joplin_UT/store/joplin-ut.braga_1.5.0_all.click
```

- **Nome do Pacote**: `joplin-ut.braga`
- **Versão**: `1.5.0`
- **Arquitetura**: `all` (Python 3 + QML / Lomiri Components)
- **Framework**: `ubuntu-touch-24.04-1.x`
- **Política AppArmor**: `2404.1`

---

## 📝 Texto do Changelog para a OpenStore

Copie e cole o texto abaixo no campo **Changelog** do formulário de submissão na OpenStore:

### Versão em Português:
```markdown
### Versão 1.5.0

Novidades e melhorias desta versão:

- ℹ️ **Botão "Sobre"**: Adicionado botão de informações na barra superior do aplicativo com créditos do projeto, autoria e links clicáveis para o grupo de pesquisa Curió (https://curio.ia.br) e currículo Lattes.
- 📂 **Memória do Último Caderno**: Ao abrir o aplicativo, ele agora inicia diretamente no último caderno ou tag selecionada pelo usuário.
- 🏷️ **Gestão Completa de Tags**: Criação, associação, renomeação e exclusão de tags sincronizadas com o padrão Joplin (type 5 e 6).
- 📁 **Gestão de Cadernos e Subcadernos**: Suporte completo a árvore hierárquica, criação de subcadernos, renomeação e remoção.
- 🔄 **Painel de Sincronização na Gaveta**: Exibição da data e hora da última sincronização com o Nextcloud, contador de itens pendentes e opções para sincronização incremental ou completa.
- 🚀 **Instância Única no Lomiri**: Otimização do lançador desktop (`X-Lomiri-Single-Instance=true`) evitando instâncias concorrentes.
- 📋 **Checklists e Formatação Markdown**: Suporte avançado a checklists interativos `- [ ]` / `- [x]` e recuo inteligente com tecla Tab em listas hierárquicas.
```

### English Version (opcional / OpenStore default):
```markdown
### Version 1.5.0

What's new in this release:

- ℹ️ **"About" Dialog**: Added an info action in the top header with project credits and clickable links to the Curió research group and author's Lattes CV.
- 📂 **Last Viewed Notebook Persistence**: The app now automatically opens into the last selected notebook or tag upon startup.
- 🏷️ **Tag Management**: Full support for creating, tagging, renaming, and deleting tags compatible with Joplin's standard sync protocol (types 5 and 6).
- 📁 **Folder & Subfolder Management**: Full hierarchy tree support, subfolder creation, rename, and delete actions.
- 🔄 **Sync Status Card in Drawer**: Shows exact date and time of last Nextcloud sync, pending change count, and force sync actions.
- 🚀 **Single Instance Launcher**: Configured `X-Lomiri-Single-Instance=true` for clean application switching on Lomiri.
- 📋 **Checklist & Markdown Enhancements**: Interactive `- [ ]` / `- [x]` checkboxes and Tab indentation for multi-level task lists.
```

---

## 🚀 Passo a Passo para Publicação na OpenStore

1. Acesse o portal do desenvolvedor da OpenStore:
   👉 **[https://open-store.io/manage](https://open-store.io/manage)**
2. Faça login com a sua conta mantenedora (`Tiago Braga`).
3. Localize e selecione o aplicativo **Joplin UT** (`joplin-ut.braga`).
4. Clique na aba **Releases** / **Upload New Version**.
5. Selecione o arquivo compilado:
   `store/joplin-ut.braga_1.5.0_all.click`
6. No campo **Changelog**, cole o texto acima formatado em Markdown.
7. Verifique os metadados:
   - **Framework**: `ubuntu-touch-24.04-1.x`
   - **Architecture**: `all`
8. Clique em **Submit for Review** (ou **Publish**).

---

## 🧪 Resumo da Validação Técnica Realizada

- ✅ **Testes Unitários**: 7/7 testes aprovados em `tests/test_core.py` (serialização de notas, pastas, tags, ETag WebDAV, persistência de preferências e integridade de manifesto/AppArmor).
- ✅ **Pacote Debian / Click**: Validação binária com `dpkg-deb -I` e `dpkg-deb -c` sem erros e sem permissões *world-writable* (atendendo à exigência estrita de segurança da OpenStore).
- ✅ **Single Instance**: Verificação de `X-Lomiri-Single-Instance=true` no arquivo `.desktop`.
