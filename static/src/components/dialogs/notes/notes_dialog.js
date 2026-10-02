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
                && !(this.props.notesData.detail_photos || []).length,
            // Fotos de DETALLE (defectos): viven con las notas, no en la
            // galería comercial.
            detailPhotos: this.props.notesData.detail_photos || [],
            photoComment: '',
            isUploading: false,
            preview: null,
        });
        this.changed = false;
    }

    photoSrc(photo) {
        const data = photo.image || '';
        const mime = data.startsWith('UklGR') ? 'image/webp'
            : data.startsWith('iVBOR') ? 'image/png' : 'image/jpeg';
        return `data:${mime};base64,${data}`;
    }

    openPreview(photo) {
        this.state.preview = photo;
    }

    closePreview() {
        this.state.preview = null;
    }

    onPhotoCommentInput(ev) {
        this.state.photoComment = ev.target.value;
    }

    _readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async onDetailFileChange(ev) {
        const files = Array.from(ev.target.files || []);
        ev.target.value = '';
        if (!files.length || this.state.isUploading) {
            return;
        }
        this.state.isUploading = true;
        try {
            for (const file of files) {
                const data = await this._readFile(file);
                const result = await this.orm.call(
                    "stock.quant", "save_lot_detail_photo", [],
                    {
                        quant_id: this.detailId,
                        photo_name: file.name,
                        photo_data: data,
                        notas: this.state.photoComment,
                    }
                );
                if (!result.success) {
                    this.notification.add(result.error || "No se pudo guardar la foto de detalle", { type: "danger" });
                    return;
                }
                this.state.detailPhotos = result.detail_photos || [];
                this.changed = true;
            }
            this.state.photoComment = '';
            this.notification.add("Foto de detalle guardada", { type: "success" });
        } catch (error) {
            console.error("Error al guardar foto de detalle:", error);
            this.notification.add("Error al guardar la foto de detalle", { type: "danger" });
        } finally {
            this.state.isUploading = false;
        }
    }

    async deleteDetailPhoto(photo, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        try {
            const result = await this.orm.call(
                "stock.quant", "delete_lot_detail_photo", [], { photo_id: photo.id });
            if (!result.success) {
                this.notification.add(result.error || "No se pudo eliminar", { type: "danger" });
                return;
            }
            this.state.detailPhotos = result.detail_photos || [];
            this.state.preview = null;
            this.changed = true;
        } catch (error) {
            console.error("Error al eliminar foto de detalle:", error);
            this.notification.add("No tienes permiso para eliminar esta foto de detalle", { type: "danger" });
        }
    }

    async closeDialog() {
        this.props.close();
        if (this.changed && this.props.onReload) {
            await this.props.onReload();
        }
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