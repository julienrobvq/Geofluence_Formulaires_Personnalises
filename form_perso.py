from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QFileDialog
)
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsAttributeEditorContainer,
    QgsAttributeEditorField, QgsEditFormConfig
)
from pathlib import Path

# --- Fenêtre de sélection de couche
class FormLayerSelector(QDialog):
    def __init__(self, layers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner un formulaire")
        self.resize(350, 100)

        self.layout = QVBoxLayout()
        self.label = QLabel("Sélectionner un formulaire")
        self.layout.addWidget(self.label)

        self.combo = QComboBox()
        for layer in layers:
            self.combo.addItem(layer.name(), layer)
        self.layout.addWidget(self.combo)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttons)

        self.setLayout(self.layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def selected_layer(self):
        return self.combo.currentData()

# --- Fenêtre de visualisation de la structure du formulaire avec coches
class FormStructureDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Structure du formulaire : {layer.name()}")
        self.resize(500, 600)

        self.layer = layer
        self.layout = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Conteneur / Champ", "Alias"])
        self.tree.itemChanged.connect(self.on_item_check_changed)

        self.layout.addWidget(self.tree)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.populate_tree()

    def make_checkable_item(self, name, alias=""):
        item = QTreeWidgetItem([name, alias])
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(0, Qt.Checked)
        return item

    def populate_tree(self):
        def process_container(container, parent_item):
            children = getattr(container, "children", lambda: [])()
            for child in children:
                if isinstance(child, QgsAttributeEditorContainer):
                    item = self.make_checkable_item(child.name())
                    parent_item.addChild(item)
                    process_container(child, item)
                elif isinstance(child, QgsAttributeEditorField):
                    field_name = child.name()
                    if self.layer.fields().indexOf(field_name) != -1:
                        alias = self.layer.fields().field(field_name).alias()
                    else:
                        alias = "(champ inconnu)"
                    item = self.make_checkable_item(field_name, alias)
                    parent_item.addChild(item)

        config = self.layer.editFormConfig()
        for tab in config.tabs():
            tab_item = self.make_checkable_item(tab.name())
            self.tree.addTopLevelItem(tab_item)
            process_container(tab, tab_item)
        self.tree.expandAll()

    def on_item_check_changed(self, item, column):
        state = item.checkState(0)
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)

    def get_checked_paths(self):
        def collect_checked(item, path=""):
            current_path = f"{path}{item.text(0)}"
            checked = []
            if item.checkState(0) == Qt.Checked and item.childCount() == 0:
                checked.append(current_path)
            for i in range(item.childCount()):
                checked += collect_checked(item.child(i), current_path + "/")
            return checked

        paths = []
        for i in range(self.tree.topLevelItemCount()):
            paths += collect_checked(self.tree.topLevelItem(i))
        return paths

# Exécution principale
form_layers = [
    lyr for lyr in QgsProject.instance().mapLayers().values()
    if lyr.name().startswith("Form_") and isinstance(lyr, QgsVectorLayer)
]

if not form_layers:
    iface.messageBar().pushWarning("Sélection Form_", "Aucune couche ne commence par 'Form_'.")
else:
    sel_dialog = FormLayerSelector(form_layers)
    if sel_dialog.exec_():
        selected_layer = sel_dialog.selected_layer()
        iface.setActiveLayer(selected_layer)

        form_dialog = FormStructureDialog(selected_layer)
        if form_dialog.exec_():
            checked_paths = form_dialog.get_checked_paths()
            print("Champs cochés :")
            for p in checked_paths:
                print(" -", p)
            iface.messageBar().pushInfo("Champs cochés", f"{len(checked_paths)} champ(s) cochés")

            new_cfg = QgsEditFormConfig()
            new_cfg.setLayout(QgsEditFormConfig.TabLayout)

            for path in checked_paths:
                field_name = path.split("/")[-1]
                idx = selected_layer.fields().indexOf(field_name)
                if idx != -1:
                    field_element = QgsAttributeEditorField(field_name, idx, None)
                    new_cfg.addTab(field_element)

            selected_layer.setEditFormConfig(new_cfg)
            iface.messageBar().pushSuccess("Formulaire modifié", f"Le formulaire de la couche '{selected_layer.name()}' a été mis à jour.")