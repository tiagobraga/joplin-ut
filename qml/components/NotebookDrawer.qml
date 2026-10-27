import QtQuick 2.12
import Lomiri.Components 1.3
import Lomiri.Components.ListItems 1.3 as ListItem

Rectangle {
    id: drawer
    width: Math.min(parent.width * 0.85, units.gu(38))
    height: parent.height
    color: theme.palette.normal.background

    signal folderSelected(string folderId, string folderTitle)
    signal newFolderRequested()
    signal folderOptionsRequested(string folderId, string folderTitle)

    property var foldersModel: []
    property string selectedFolderId: ""
    property var collapsedMap: ({})
    property bool allCollapsed: false

    // Modelo nativo C++ para garantir atualização visual imediata ao expandir/recolher
    ListModel {
        id: visibleFoldersModel
    }

    onFoldersModelChanged: {
        rebuildVisibleFolders();
    }

    function isFolderVisible(item, cmap) {
        if (!item || !item.parent_id) return true;
        var p = String(item.parent_id || "");
        var safety = 0;
        while (p !== "" && safety < 20) {
            safety++;
            if (cmap && cmap[p] === true) {
                return false;
            }
            var parentObj = null;
            for (var i = 0; i < foldersModel.length; i++) {
                if (foldersModel[i] && String(foldersModel[i].id) === p) {
                    parentObj = foldersModel[i];
                    break;
                }
            }
            p = parentObj ? String(parentObj.parent_id || "") : "";
        }
        return true;
    }

    function rebuildVisibleFolders() {
        visibleFoldersModel.clear();
        if (!foldersModel || foldersModel.length === 0) return;

        var anyParentExpanded = false;
        var hasAnyParent = false;

        for (var i = 0; i < foldersModel.length; i++) {
            var f = foldersModel[i];
            if (!f) continue;
            var fId = String(f.id || "");
            var hasChildren = Boolean(f.has_children);
            var isCollapsed = Boolean(collapsedMap && collapsedMap[fId] === true);

            if (hasChildren) {
                hasAnyParent = true;
                if (!isCollapsed) {
                    anyParentExpanded = true;
                }
            }

            if (isFolderVisible(f, collapsedMap)) {
                visibleFoldersModel.append({
                    "id": fId,
                    "title": String(f.title || "Sem Nome"),
                    "parent_id": String(f.parent_id || ""),
                    "level": Number(f.level || 0),
                    "has_children": hasChildren,
                    "notes_count": Number(f.notes_count || 0),
                    "is_collapsed": isCollapsed
                });
            }
        }

        allCollapsed = hasAnyParent && !anyParentExpanded;
    }

    function toggleCollapse(folderId) {
        var targetId = String(folderId || "");
        if (!targetId) return;

        var nextMap = {};
        if (collapsedMap) {
            for (var k in collapsedMap) {
                if (collapsedMap.hasOwnProperty(k) && collapsedMap[k] === true) {
                    nextMap[k] = true;
                }
            }
        }

        if (nextMap[targetId] === true) {
            delete nextMap[targetId];
        } else {
            nextMap[targetId] = true;
        }

        collapsedMap = nextMap;
        console.log("[Joplin UT] toggleCollapse folder=" + targetId + " collapsed=" + Boolean(nextMap[targetId]));
        rebuildVisibleFolders();
    }

    function toggleCollapseAll() {
        var nextCollapsedState = !allCollapsed;
        var nextMap = {};
        if (nextCollapsedState && foldersModel) {
            for (var i = 0; i < foldersModel.length; i++) {
                if (foldersModel[i] && foldersModel[i].has_children) {
                    nextMap[String(foldersModel[i].id)] = true;
                }
            }
        }
        collapsedMap = nextMap;
        allCollapsed = nextCollapsedState;
        console.log("[Joplin UT] toggleCollapseAll allCollapsed=" + allCollapsed);
        rebuildVisibleFolders();
    }

    // Cabeçalho azul da gaveta
    Rectangle {
        id: drawerHeader
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: units.gu(10)
        color: "#1B5EBF"

        Column {
            anchors.left: parent.left
            anchors.leftMargin: units.gu(2)
            anchors.verticalCenter: parent.verticalCenter
            spacing: units.gu(0.5)

            Label {
                text: "Joplin UT"
                fontSize: "x-large"
                color: "#FFFFFF"
                font.bold: true
            }
            Label {
                text: "Cadernos de Notas"
                fontSize: "small"
                color: "#E0E8F5"
            }
        }
    }

    // Botão inferior Novo Caderno
    Button {
        id: btnNewFolder
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: units.gu(2)
        text: "+ Novo Caderno"
        color: LomiriColors.orange
        onClicked: drawer.newFolderRequested()
    }

    // Área rolável com lista de cadernos
    Flickable {
        id: drawerFlickable
        anchors.top: drawerHeader.bottom
        anchors.bottom: btnNewFolder.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottomMargin: units.gu(1)
        contentHeight: drawerContentCol.height
        clip: true

        Column {
            id: drawerContentCol
            width: parent.width

            // Opção "Todas as Notas"
            ListItem.Standard {
                text: "Todas as Notas"
                iconName: "note"
                selected: drawer.selectedFolderId === ""
                onClicked: {
                    drawer.selectedFolderId = ""
                    drawer.folderSelected("", "Todas as Notas")
                }
            }

            // Cabeçalho de seção com botão para Recolher/Expandir Tudo
            Rectangle {
                width: parent.width
                height: units.gu(4.5)
                color: "transparent"

                Label {
                    anchors.left: parent.left
                    anchors.leftMargin: units.gu(2)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "ESTRUTURA DE CADERNOS"
                    fontSize: "small"
                    font.bold: true
                    color: LomiriColors.slate
                }

                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: units.gu(1.5)
                    anchors.verticalCenter: parent.verticalCenter
                    width: collapseAllLabel.width + units.gu(2)
                    height: units.gu(3.4)
                    radius: units.gu(0.6)
                    color: collapseAllMouse.pressed ? "#D0E0F8" : "#E8F0FE"

                    Label {
                        id: collapseAllLabel
                        anchors.centerIn: parent
                        text: drawer.allCollapsed ? "Expandir tudo" : "Recolher tudo"
                        fontSize: "small"
                        font.bold: true
                        color: "#1B5EBF"
                    }

                    MouseArea {
                        id: collapseAllMouse
                        anchors.fill: parent
                        onClicked: drawer.toggleCollapseAll()
                    }
                }
            }

            // Lista Hierárquica com Expandir/Recolher reativo via ListModel
            Repeater {
                model: visibleFoldersModel
                delegate: Rectangle {
                    id: folderRowItem
                    width: drawer.width
                    height: units.gu(5.5)
                    clip: true
                    color: drawer.selectedFolderId === model.id ? LomiriColors.porcelain : (rowMouseArea.pressed ? LomiriColors.porcelain : "transparent")

                    // Indicador azul de caderno ativo
                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: units.dp(4)
                        color: "#1B5EBF"
                        visible: drawer.selectedFolderId === model.id
                    }

                    // Conteúdo visual da linha
                    Item {
                        id: rowContent
                        anchors.fill: parent
                        anchors.leftMargin: units.gu(1.2) + ((model.level || 0) * units.gu(2.2))
                        anchors.rightMargin: units.gu(2)

                        // Botão visual de Expandir / Recolher para pastas com subpastas
                        Rectangle {
                            id: expandBtn
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            width: units.gu(3.6)
                            height: units.gu(3.6)
                            radius: units.gu(0.6)
                            color: model.has_children ? (expandMouseArea.pressed ? "#D0E0F8" : "#E8F0FE") : "transparent"

                            Label {
                                anchors.centerIn: parent
                                text: model.is_collapsed ? "▶" : "▼"
                                fontSize: "small"
                                font.bold: true
                                color: "#1B5EBF"
                                visible: model.has_children === true
                            }

                            Label {
                                anchors.centerIn: parent
                                text: "↳"
                                fontSize: "medium"
                                font.bold: true
                                color: LomiriColors.slate
                                visible: (model.level || 0) > 0 && model.has_children !== true
                            }
                        }

                        // Ícone da pasta
                        Icon {
                            id: folderIcon
                            anchors.left: expandBtn.right
                            anchors.leftMargin: units.gu(0.6)
                            anchors.verticalCenter: parent.verticalCenter
                            name: "folder"
                            width: units.gu(2.4)
                            height: units.gu(2.4)
                            color: (model.level || 0) === 0 ? "#1B5EBF" : LomiriColors.slate
                        }

                        // Contagem de notas do caderno
                        Label {
                            id: countLabel
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: model.notes_count ? model.notes_count.toString() : "0"
                            color: theme.palette.normal.baseText
                            fontSize: "small"
                            opacity: 0.55
                        }

                        // Título do caderno (ocupa todo o espaço central)
                        Label {
                            anchors.left: folderIcon.right
                            anchors.leftMargin: units.gu(1)
                            anchors.right: countLabel.left
                            anchors.rightMargin: units.gu(1)
                            anchors.verticalCenter: parent.verticalCenter
                            text: model.title || "Sem Nome"
                            font.bold: (model.level || 0) === 0
                            fontSize: "medium"
                            elide: Text.ElideRight
                            color: theme.palette.normal.baseText
                        }
                    }

                    // Área de toque exclusiva para Expandir / Recolher (sem sobreposição com rowMouseArea!)
                    MouseArea {
                        id: expandMouseArea
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: model.has_children ? (units.gu(1.2) + ((model.level || 0) * units.gu(2.2)) + units.gu(6.8)) : 0
                        enabled: model.has_children === true
                        visible: model.has_children === true
                        z: 10
                        onClicked: {
                            drawer.toggleCollapse(model.id)
                        }
                    }

                    // Área de toque para selecionar o caderno (à direita do botão de expandir)
                    MouseArea {
                        id: rowMouseArea
                        anchors.left: model.has_children ? expandMouseArea.right : parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        z: 5
                        onClicked: {
                            drawer.selectedFolderId = model.id
                            drawer.folderSelected(model.id, model.title)
                        }
                        onPressAndHold: {
                            drawer.folderOptionsRequested(model.id, model.title)
                        }
                    }

                    // Linha divisória fina
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: units.dp(1)
                        color: theme.palette.normal.baseText
                        opacity: 0.08
                    }
                }
            }
        }
    }
}
