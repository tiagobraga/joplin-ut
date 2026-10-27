import QtQuick 2.12
import Lomiri.Components 1.3
import Lomiri.Components.Popups 1.3

Page {
    id: notesListPage
    title: currentFolderTitle

    property string currentFolderId: ""
    property string currentFolderTitle: "Todas as Notas"
    property bool isSearching: false
    property bool isSyncing: false
    property string syncStatusText: ""

    // Modelo nativo e reativo do Qt Quick (garante reconstrução visual imediata dos itens)
    ListModel {
        id: notesListModel
    }

    // Cache puro em JavaScript (evita usar notesListModel.get(i), que é invalidado após clear())
    property var cachedNotes: []

    // Preferências de ordenação
    property string sortBy: "updated_time"   // "updated_time", "created_time", "title"
    property string sortOrder: "DESC"       // "DESC", "ASC"

    signal toggleDrawer()
    signal openSettings()
    signal openNote(string noteId, string folderId)

    // Recarrega notas assim que o backend Python estiver pronto
    Connections {
        target: root
        onIsReadyChanged: {
            if (root.isReady) {
                notesListPage.loadSortPreferences(true);
            }
        }
    }

    // Recarrega as notas sempre que a página volta a ficar visível
    onVisibleChanged: {
        if (visible && root.isReady) {
            notesListPage.loadNotes();
        }
    }

    header: PageHeader {
        id: pageHeader
        title: notesListPage.isSearching ? "" : notesListPage.currentFolderTitle

        leadingActionBar.actions: [
            Action {
                iconName: "navigation-menu"
                text: "Menu"
                onTriggered: notesListPage.toggleDrawer()
            }
        ]

        trailingActionBar.actions: [
            Action {
                iconName: "find"
                text: "Buscar"
                onTriggered: {
                    notesListPage.isSearching = !notesListPage.isSearching
                    if (!notesListPage.isSearching) {
                        searchField.text = ""
                        notesListPage.loadNotes()
                    }
                }
            },
            Action {
                iconName: "reload"
                text: "Sincronizar"
                enabled: !notesListPage.isSyncing
                onTriggered: triggerSync()
            },
            Action {
                iconName: "settings"
                text: "Configurações"
                onTriggered: notesListPage.openSettings()
            }
        ]

        // Barra de pesquisa embutida no cabeçalho
        contents: Item {
            anchors.fill: parent
            visible: notesListPage.isSearching

            TextField {
                id: searchField
                anchors.left: parent.left
                anchors.right: clearSearchBtn.left
                anchors.rightMargin: units.gu(1)
                anchors.verticalCenter: parent.verticalCenter
                placeholderText: "Pesquisar nas notas..."
                hasClearButton: true
                onTextChanged: notesListPage.loadNotes()
            }

            Button {
                id: clearSearchBtn
                anchors.right: parent.right
                anchors.rightMargin: units.gu(1)
                anchors.verticalCenter: parent.verticalCenter
                text: "Fechar"
                onClicked: {
                    notesListPage.isSearching = false
                    searchField.text = ""
                    notesListPage.loadNotes()
                }
            }
        }
    }

    function getSortFieldLabel() {
        if (sortBy === "created_time") return "Criação";
        if (sortBy === "title") return "Título";
        return "Atualização";
    }

    function getSortDirectionLabel() {
        if (sortBy === "title") {
            return sortOrder === "ASC" ? "A → Z" : "Z → A";
        }
        return sortOrder === "DESC" ? "⬇ Recentes" : "⬆ Antigas";
    }

    // Clona um item de nota garantindo tipos primitivos definidos (nunca undefined)
    function cloneNoteItem(item) {
        if (!item) return null;
        return {
            "id": String(item.id || ""),
            "parent_id": String(item.parent_id || ""),
            "title": String(item.title || "Sem Título"),
            "preview": String(item.preview || ""),
            "created_time": String(item.created_time || ""),
            "updated_time": String(item.updated_time || ""),
            "date_display": String(item.date_display || ""),
            "is_todo": Number(item.is_todo || 0),
            "todo_completed": Number(item.todo_completed || 0),
            "dirty": Number(item.dirty || 0)
        };
    }

    // Reconstrói o ListModel com objetos JS puros clonados
    function rebuildListModel(list) {
        var cleanList = [];
        if (list && list.length > 0) {
            for (var i = 0; i < list.length; i++) {
                var cloned = cloneNoteItem(list[i]);
                if (cloned) {
                    cleanList.push(cloned);
                }
            }
        }
        notesListPage.cachedNotes = cleanList;
        notesListModel.clear();
        for (var j = 0; j < cleanList.length; j++) {
            notesListModel.append(cleanList[j]);
        }
    }

    // Ordenação robusta em memória para resposta visual imediata no display
    function sortNotesInMemory(list, field, order) {
        if (!list || list.length === 0) return [];
        var copy = [];
        for (var i = 0; i < list.length; i++) {
            var cloned = cloneNoteItem(list[i]);
            if (cloned) {
                copy.push(cloned);
            }
        }
        var isAsc = (order === "ASC");

        copy.sort(function(a, b) {
            var valA = "";
            var valB = "";

            if (field === "title") {
                valA = (a.title || "").toLowerCase();
                valB = (b.title || "").toLowerCase();
                return isAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
            } else if (field === "created_time") {
                valA = a.created_time || "";
                valB = b.created_time || "";
            } else { // updated_time
                valA = a.updated_time || "";
                valB = b.updated_time || "";
            }

            if (valA < valB) return isAsc ? -1 : 1;
            if (valA > valB) return isAsc ? 1 : -1;
            return 0;
        });

        return copy;
    }

    // Alterna o campo de ordenação com 1 toque direto (Atualização -> Criação -> Título)
    function cycleSortField() {
        var nextField = "updated_time";
        if (sortBy === "updated_time") {
            nextField = "created_time";
        } else if (sortBy === "created_time") {
            nextField = "title";
        } else {
            nextField = "updated_time";
        }
        applySort(nextField, sortOrder);
    }

    // Inverte a direção de ordenação com 1 toque direto
    function toggleSortDirection() {
        var nextOrder = (sortOrder === "DESC") ? "ASC" : "DESC";
        applySort(sortBy, nextOrder);
    }

    function loadSortPreferences(shouldLoadNotes) {
        if (!root.isReady) return;
        py.call('main.get_app_settings', [], function(s) {
            if (s) {
                notesListPage.sortBy = s.sort_by || "updated_time";
                notesListPage.sortOrder = s.sort_order || "DESC";
            }
            if (shouldLoadNotes) {
                notesListPage.loadNotes();
            }
        });
    }

    function applySort(newSortBy, newSortOrder) {
        if (newSortBy) notesListPage.sortBy = newSortBy;
        if (newSortOrder) notesListPage.sortOrder = newSortOrder;

        console.log("[Joplin UT] Aplicando ordenação: " + notesListPage.sortBy + " " + notesListPage.sortOrder);

        // 1. Ordena imediatamente a partir do cache puro JS (sem usar ponteiros de notesListModel.get)
        var sorted = sortNotesInMemory(notesListPage.cachedNotes, notesListPage.sortBy, notesListPage.sortOrder);
        rebuildListModel(sorted);

        if (notesList) {
            notesList.positionViewAtBeginning();
        }

        // 2. Salva a preferência no disco e recarrega do SQLite para atualizar date_display
        py.call('main.save_sort_preferences', [notesListPage.sortBy, notesListPage.sortOrder], function(res) {
            console.log("[Joplin UT] Preferência salva no disco com sucesso.");
            notesListPage.loadNotes();
        });
    }

    function loadNotes() {
        if (!root.isReady) return;
        var query = (searchField && searchField.text) ? searchField.text : "";
        var targetFolder = notesListPage.currentFolderId ? notesListPage.currentFolderId : "";
        var activeSortBy = notesListPage.sortBy ? notesListPage.sortBy : "updated_time";
        var activeSortOrder = notesListPage.sortOrder ? notesListPage.sortOrder : "DESC";

        console.log("[Joplin UT] loadNotes: folder=" + targetFolder + " sort=" + activeSortBy + " " + activeSortOrder);

        py.call('main.get_notes_list', [
            targetFolder,
            query,
            activeSortBy,
            activeSortOrder
        ], function(notes) {
            console.log("[Joplin UT] loadNotes retornou " + (notes ? notes.length : 0) + " notas");

            var sorted = sortNotesInMemory(notes || [], activeSortBy, activeSortOrder);
            rebuildListModel(sorted);

            if (notesList) {
                notesList.positionViewAtBeginning();
            }
        });
    }

    function triggerSync() {
        if (isSyncing) return;
        isSyncing = true;
        syncStatusText = "Sincronizando com o Nextcloud...";
        syncBanner.visible = true;

        py.call('main.perform_sync', [false], function(res) {
            isSyncing = false;
            if (res && res.success) {
                syncStatusText = res.message;
                notesListPage.loadNotes();
                root.refreshFolders();
            } else {
                syncStatusText = (res && res.message) ? res.message : "Erro de sincronização.";
            }
            hideSyncBannerTimer.restart();
        });
    }

    Timer {
        id: hideSyncBannerTimer
        interval: 5000
        repeat: false
        onTriggered: syncBanner.visible = false
    }

    // Layout principal
    Item {
        anchors.fill: parent

        // Banner informativo de sincronização
        Rectangle {
            id: syncBanner
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: Math.max(syncBannerRow.height + units.gu(2), units.gu(4.5))
            visible: false
            color: notesListPage.isSyncing ? "#E8F0FE" : "#E6F4EA"
            z: 10

            Row {
                id: syncBannerRow
                anchors.centerIn: parent
                spacing: units.gu(1)
                width: parent.width - units.gu(4)

                ActivityIndicator {
                    running: notesListPage.isSyncing
                    visible: notesListPage.isSyncing
                }

                Label {
                    id: syncLabel
                    width: parent.width - (parent.children[0].visible ? units.gu(4) : 0)
                    text: notesListPage.syncStatusText
                    color: notesListPage.isSyncing ? "#1A73E8" : "#137333"
                    fontSize: "small"
                    font.bold: true
                    wrapMode: Text.Wrap
                }
            }
        }

        // Barra de Subcabeçalho com Contagem e Botões Nativos de Ordenação
        Rectangle {
            id: subheaderBar
            anchors.top: syncBanner.visible ? syncBanner.bottom : parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: units.gu(5)
            color: theme.palette.normal.background
            z: 5

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: units.dp(1)
                color: theme.palette.normal.baseText
                opacity: 0.1
            }

            // Contagem reativa de notas via ListModel
            Label {
                anchors.left: parent.left
                anchors.leftMargin: units.gu(2)
                anchors.verticalCenter: parent.verticalCenter
                text: notesListModel.count + " notas"
                fontSize: "small"
                color: LomiriColors.slate
                font.bold: true
            }

            // Botões Nativos de Ordenação à direita
            Row {
                anchors.right: parent.right
                anchors.rightMargin: units.gu(1.5)
                anchors.verticalCenter: parent.verticalCenter
                spacing: units.gu(1)

                // Botão de Critério (Alterna: Atualização -> Criação -> Título)
                Button {
                    height: units.gu(3.8)
                    text: "⇅ " + notesListPage.getSortFieldLabel()
                    color: LomiriColors.porcelain
                    onClicked: notesListPage.cycleSortField()
                }

                // Botão de Direção (Alterna: Recentes <-> Antigas / A-Z <-> Z-A)
                Button {
                    height: units.gu(3.8)
                    text: notesListPage.getSortDirectionLabel()
                    color: LomiriColors.orange
                    onClicked: notesListPage.toggleSortDirection()
                }
            }
        }

        // Lista de Notas com Cards Personalizados e Título em Destaque
        ListView {
            id: notesList
            anchors.top: subheaderBar.bottom
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            clip: true
            model: notesListModel

            delegate: Rectangle {
                id: noteCardItem
                width: notesList.width
                height: units.gu(8.5)
                color: mouseAreaNote.pressed ? LomiriColors.porcelain : "transparent"

                Column {
                    anchors.fill: parent
                    anchors.leftMargin: units.gu(2)
                    anchors.rightMargin: units.gu(2)
                    anchors.topMargin: units.gu(1.2)
                    anchors.bottomMargin: units.gu(1.2)
                    spacing: units.gu(0.4)

                    // Linha 1: Título e Data
                    Item {
                        width: parent.width
                        height: Math.max(titleRow.height, dateLabel.height)

                        Row {
                            id: titleRow
                            anchors.left: parent.left
                            anchors.right: dateLabel.left
                            anchors.rightMargin: units.gu(1)
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: units.gu(0.8)

                            // Ícone de To-Do se for tarefa
                            Icon {
                                name: model.todo_completed ? "ok" : "edit-select-all"
                                width: units.gu(2)
                                height: units.gu(2)
                                anchors.verticalCenter: parent.verticalCenter
                                visible: model.is_todo === 1
                                color: model.todo_completed ? LomiriColors.green : LomiriColors.slate
                            }

                            // TÍTULO DA NOTA (em negrito e tamanho legível)
                            Label {
                                text: model.title || "Sem Título"
                                font.bold: true
                                fontSize: "medium"
                                color: theme.palette.normal.baseText
                                elide: Text.ElideRight
                                width: parent.width - (model.is_todo === 1 ? units.gu(2.8) : 0)
                            }
                        }

                        // Data formatada da nota no canto direito
                        Label {
                            id: dateLabel
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: model.date_display || ""
                            fontSize: "small"
                            color: LomiriColors.slate
                            opacity: 0.75
                        }
                    }

                    // Linha 2: Prévia limpa do texto da nota (até 2 linhas)
                    Label {
                        width: parent.width
                        text: model.preview || "Nota vazia"
                        fontSize: "small"
                        color: theme.palette.normal.baseText
                        opacity: 0.6
                        elide: Text.ElideRight
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                    }
                }

                // Ponto indicador para modificações locais pendentes
                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: units.gu(1.5)
                    anchors.verticalCenter: parent.verticalCenter
                    width: units.gu(0.8)
                    height: units.gu(0.8)
                    radius: width / 2
                    color: LomiriColors.orange
                    visible: model.dirty === 1
                }

                // Linha divisória sutil entre as notas
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: units.dp(1)
                    color: theme.palette.normal.baseText
                    opacity: 0.08
                }

                MouseArea {
                    id: mouseAreaNote
                    anchors.fill: parent
                    onClicked: {
                        notesListPage.openNote(model.id, model.parent_id);
                    }
                }
            }

            // Mensagem quando o caderno estiver vazio
            Item {
                anchors.centerIn: parent
                visible: notesListModel.count === 0
                width: parent.width - units.gu(4)
                height: units.gu(20)

                Column {
                    anchors.centerIn: parent
                    spacing: units.gu(1.5)
                    width: parent.width

                    Icon {
                        name: notesListPage.isSearching ? "find" : "note"
                        width: units.gu(6)
                        height: units.gu(6)
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: LomiriColors.slate
                        opacity: 0.4
                    }
                    Label {
                        text: notesListPage.isSearching ? "Nenhuma nota encontrada" : "Nenhuma nota neste caderno"
                        color: LomiriColors.slate
                        opacity: 0.6
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Button {
                        text: notesListPage.isSyncing ? "Sincronizando..." : "Sincronizar com o Nextcloud"
                        color: "#1B5EBF"
                        anchors.horizontalCenter: parent.horizontalCenter
                        enabled: !notesListPage.isSyncing
                        visible: !notesListPage.isSearching
                        onClicked: triggerSync()
                    }
                }
            }
        }
    }

    // Botão flutuante para Nova Nota
    Button {
        id: fabNewNote
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: units.gu(2.5)
        width: units.gu(6.5)
        height: units.gu(6.5)
        color: "#1B5EBF"
        z: 20

        Icon {
            name: "add"
            color: "#FFFFFF"
            anchors.centerIn: parent
            width: units.gu(3)
            height: units.gu(3)
        }

        onClicked: {
            notesListPage.openNote("", notesListPage.currentFolderId)
        }
    }

    Component.onCompleted: {
        if (root.isReady) {
            loadSortPreferences(true);
        }
    }
}
