from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QInputDialog
)
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsAttributeEditorContainer,
    QgsAttributeEditorField, QgsEditFormConfig
)

# --- Fenêtre de sélection de couche
class FormLayerSelector(QDialog):
    def __init__(self, layers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner un formulaire")
        self.resize(350, 100)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sélectionner un formulaire"))

        self.combo = QComboBox()
        for layer in layers:
            self.combo.addItem(layer.name(), layer)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def selected_layer(self):
        return self.combo.currentData()

# --- Fenêtre de structure du formulaire
class FormStructureDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Structure du formulaire : {layer.name()}")
        self.resize(800, 600)

        self.layer = layer
        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Conteneur / Champ", "Alias"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().Stretch)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeToContents)

        self.tree.itemChanged.connect(self.on_item_check_changed)
        layout.addWidget(self.tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.populate_tree()

    def make_item(self, name, alias=""):
        item = QTreeWidgetItem([name, alias])
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(0, Qt.Checked)
        return item

    def populate_tree(self):
        def has_field(container):
            for child in container.children():
                if isinstance(child, QgsAttributeEditorField):
                    return True
                if isinstance(child, QgsAttributeEditorContainer) and has_field(child):
                    return True
            return False

        def process_container(container, parent):
            for child in container.children():
                if isinstance(child, QgsAttributeEditorContainer):
                    if not has_field(child):
                        continue  # ignorer conteneur vide

                    item = self.make_item(child.name())
                    parent.addChild(item)
                    process_container(child, item)

                elif isinstance(child, QgsAttributeEditorField):
                    fname = child.name()
                    if self.layer.fields().indexOf(fname) == -1:
                        continue

                    alias = self.layer.fields().field(fname).alias()
                    parent.addChild(self.make_item(fname, alias))

        cfg = self.layer.editFormConfig()

        for tab in cfg.tabs():
            if not has_field(tab):
                continue  # ignorer onglet vide

            tab_item = self.make_item(tab.name())
            self.tree.addTopLevelItem(tab_item)
            process_container(tab, tab_item)

        self.tree.expandAll()

    def on_item_check_changed(self, item, column):
        state = item.checkState(0)
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)

    def get_checked_fields(self):
        fields = []

        def walk(item):
            if item.childCount() == 0 and item.checkState(0) == Qt.Checked:
                fields.append(item.text(0))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))

        return fields
# --- Duplication logique + formulaire simplifié
def duplicate_layer_in_project(source_layer, field_names):
    name, ok = QInputDialog.getText(
        None,
        "Nom de la couche dupliquée",
        "Nom de la nouvelle couche :",
        text=f"{source_layer.name()}_simplifie"
    )
    if not ok:
        return None

    dup = source_layer.clone()
    dup.setName(name)
    QgsProject.instance().addMapLayer(dup)

    cfg = QgsEditFormConfig()
    cfg.setLayout(QgsEditFormConfig.TabLayout)

    for fname in field_names:
        idx = dup.fields().indexOf(fname)
        if idx != -1:
            cfg.addTab(QgsAttributeEditorField(fname, idx, None))

    dup.setEditFormConfig(cfg)
    return dup

# ------------------------
# Exécution principale
# ------------------------
form_layers = [
    l for l in QgsProject.instance().mapLayers().values()
    if isinstance(l, QgsVectorLayer) and l.name().startswith("Form_")
]

if not form_layers:
    iface.messageBar().pushWarning("Formulaire", "Aucune couche Form_ trouvée.")
else:
    sel = FormLayerSelector(form_layers)
    if sel.exec_():
        layer = sel.selected_layer()
        dlg = FormStructureDialog(layer)
        if dlg.exec_():
            fields = dlg.get_checked_fields()
            dup = duplicate_layer_in_project(layer, fields)
            if dup:
                iface.messageBar().pushSuccess(
                    "Formulaire simplifié",
                    f"Couche '{dup.name()}' créée (duplication logique)."
                )
