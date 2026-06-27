/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class BlockPhotoDialog extends Component {
    setup() {
        this.state = useState({ zoom: null });
    }

    get title() {
        return `Fotos del bloque ${this.props.blockName || ""}`.trim();
    }

    src(photo) {
        return `data:image/jpeg;base64,${photo.image}`;
    }

    openZoom(index) {
        this.state.zoom = index;
    }

    closeZoom() {
        this.state.zoom = null;
    }
}

BlockPhotoDialog.template = "inventory_visual_enhanced.BlockPhotoDialog";
BlockPhotoDialog.components = { Dialog };
BlockPhotoDialog.props = {
    blockName: { type: String, optional: true },
    photos: { type: Array, optional: true },
    close: { type: Function, optional: true },
    "*": true,
};
