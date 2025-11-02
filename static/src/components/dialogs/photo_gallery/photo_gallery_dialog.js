/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class PhotoGalleryDialog extends Component {
    setup() {
        this.photosData = this.props.photosData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            photoName: `Foto - ${this.photosData.lot_name}`,
            selectedFile: null,
            isUploading: false,
            showUploadForm: false,
            currentImageIndex: 0,
        });
    }
    
    get hasPhotos() {
        return this.photosData.photos && this.photosData.photos.length > 0;
    }
    
    get currentPhoto() {
        if (!this.hasPhotos) return null;
        return this.photosData.photos[this.state.currentImageIndex];
    }
    
    toggleUploadForm() {
        this.state.showUploadForm = !this.state.showUploadForm;
        if (!this.state.showUploadForm) {
            this.state.selectedFile = null;
            this.state.photoName = `Foto - ${this.photosData.lot_name}`;
        }
    }
    
    nextPhoto() {
        if (this.state.currentImageIndex < this.photosData.photos.length - 1) {
            this.state.currentImageIndex++;
        }
    }
    
    prevPhoto() {
        if (this.state.currentImageIndex > 0) {
            this.state.currentImageIndex--;
        }
    }
    
    onFileSelected(ev) {
        this.state.selectedFile = ev.target.files[0];
    }
    
    onPhotoNameChange(ev) {
        this.state.photoName = ev.target.value;
    }
    
    async uploadPhoto() {
        if (!this.state.selectedFile) {
            this.notification.add("Por favor selecciona una imagen", { type: "warning" });
            return;
        }
        
        this.state.isUploading = true;
        
        const reader = new FileReader();
        reader.onload = async (e) => {
            const base64Data = e.target.result.split(',')[1];
            
            try {
                const result = await this.orm.call(
                    "stock.quant",
                    "save_lot_photo",
                    [],
                    {
                        quant_id: this.detailId,
                        photo_name: this.state.photoName,
                        photo_data: base64Data,
                        sequence: 10,
                        notas: ''
                    }
                );
                
                if (result.success) {
                    this.notification.add(result.message, { type: "success" });
                    this.props.close();
                    if (this.props.onReload) {
                        await this.props.onReload();
                    }
                } else {
                    this.notification.add(result.error || "Error al subir foto", { type: "danger" });
                }
            } catch (error) {
                console.error("Error al subir foto:", error);
                this.notification.add("Error al subir foto", { type: "danger" });
            } finally {
                this.state.isUploading = false;
            }
        };
        reader.readAsDataURL(this.state.selectedFile);
    }
    
    openImageInNewTab(imageData) {
        window.open(`data:image/png;base64,${imageData}`, '_blank');
    }
}

PhotoGalleryDialog.template = "inventory_visual_enhanced.PhotoGalleryDialog";
PhotoGalleryDialog.components = { Dialog };