/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class NotesDialog extends Component {
    setup() {
        this.notesData = this.props.notesData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            notes: this.props.notesData.notes || '',
            originalNotes: this.props.notesData.notes || '',
            isSaving: false,
            isEditing: !this.props.notesData.notes
        });
    }
    
    get hasNotes() {
        return this.state.originalNotes.trim().length > 0;
    }
    
    toggleEdit() {
        this.state.isEditing = !this.state.isEditing;
        if (!this.state.isEditing) {
            this.state.notes = this.state.originalNotes;
        }
    }
    
    onNotesChange(ev) {
        this.state.notes = ev.target.value;
    }
    
    async saveNotes() {
        this.state.isSaving = true;
        
        try {
            const result = await this.orm.call(
                "stock.quant",
                "save_lot_notes",
                [],
                {
                    quant_id: this.detailId,
                    notes: this.state.notes
                }
            );
            
            if (result.success) {
                this.notification.add(result.message, { type: "success" });
                this.props.close();
                if (this.props.onReload) {
                    await this.props.onReload();
                }
            } else {
                this.notification.add(result.error || "Error al guardar notas", { type: "danger" });
            }
        } catch (error) {
            console.error("Error al guardar notas:", error);
            this.notification.add("Error al guardar notas", { type: "danger" });
        } finally {
            this.state.isSaving = false;
        }
    }
}

NotesDialog.template = "inventory_visual_enhanced.NotesDialog";
NotesDialog.components = { Dialog };