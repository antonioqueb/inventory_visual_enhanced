/** @odoo-module **/

import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class PhotoGalleryDialog extends Component {
    setup() {
        this.photosData = this.props.photosData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.canvasRef = useRef("drawingCanvas");
        this.previewRef = useRef("previewImage");
        this.editorCanvasRef = useRef("editorCanvas");
        this.editorImageRef = useRef("editorImage");
        
        this.state = useState({
            photoName: `Foto - ${this.photosData.lot_name}`,
            selectedFile: null,
            isUploading: false,
            showUploadForm: false,
            currentImageIndex: 0,
            compressionInfo: null,
            previewUrl: null,
            showEditor: false,
            
            // Editor de dibujo fullscreen
            showDrawingEditor: false,
            isDrawing: false,
            brushColor: '#FF0000',
            brushSize: 6,
            canUndo: false,
            
            // Visor fullscreen
            showFullscreenViewer: false,
        });

        this.compressionConfig = {
            maxWidth: 1280,
            maxHeight: 1280,
            quality: 0.6,
            maxSizeKB: 200,
            minQuality: 0.3,
        };

        this.canvas = null;
        this.ctx = null;
        this.drawingHistory = [];
        this.currentPath = [];
        
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        onWillUnmount(() => {
            if (this.state.previewUrl) {
                URL.revokeObjectURL(this.state.previewUrl);
            }
            document.body.style.overflow = '';
        });
    }

    get hasPhotos() {
        return this.photosData.photos && this.photosData.photos.length > 0;
    }
    
    get currentPhoto() {
        if (!this.hasPhotos) return null;
        return this.photosData.photos[this.state.currentImageIndex];
    }

    get availableColors() {
        return [
            { color: '#FF0000', name: 'Rojo' },
            { color: '#00FF00', name: 'Verde' },
            { color: '#0000FF', name: 'Azul' },
            { color: '#FFFF00', name: 'Amarillo' },
            { color: '#000000', name: 'Negro' },
            { color: '#FFFFFF', name: 'Blanco' },
        ];
    }
    
    toggleUploadForm() {
        if (!this.state.showUploadForm) {
            this.openFilePicker();
        } else {
            this.state.showUploadForm = false;
            this.resetEditor();
        }
    }

    openFilePicker() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (e) => {
            if (e.target.files[0]) {
                this.handleFileSelect(e.target.files[0]);
            }
        };
        input.click();
    }

    resetEditor() {
        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
        }
        this.state.selectedFile = null;
        this.state.photoName = `Foto - ${this.photosData.lot_name}`;
        this.state.compressionInfo = null;
        this.state.previewUrl = null;
        this.state.showEditor = false;
        this.state.showDrawingEditor = false;
        this.state.canUndo = false;
        this.drawingHistory = [];
        this.currentPath = [];
        document.body.style.overflow = '';
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

    // === VISOR FULLSCREEN ===
    
    openFullscreenViewer() {
        this.state.showFullscreenViewer = true;
        document.body.style.overflow = 'hidden';
    }
    
    closeFullscreenViewer() {
        this.state.showFullscreenViewer = false;
        document.body.style.overflow = '';
    }
    
    fullscreenNext() {
        if (this.state.currentImageIndex < this.photosData.photos.length - 1) {
            this.state.currentImageIndex++;
        }
    }
    
    fullscreenPrev() {
        if (this.state.currentImageIndex > 0) {
            this.state.currentImageIndex--;
        }
    }

    handleFileSelect(file) {
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            this.notification.add("Por favor selecciona un archivo de imagen válido", { type: "warning" });
            return;
        }

        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
        }

        this.state.selectedFile = file;
        this.state.previewUrl = URL.createObjectURL(file);
        this.state.compressionInfo = {
            originalSize: this.formatFileSize(file.size),
            originalSizeBytes: file.size,
        };
        this.state.showUploadForm = true;
        this.state.showEditor = true;
        this.drawingHistory = [];
    }
    
    onPhotoNameChange(ev) {
        this.state.photoName = ev.target.value;
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // === DESCARGA Y COMPARTIR ===

    downloadCurrentImage() {
        if (!this.currentPhoto) return;
        
        try {
            // Convertir base64 a Blob
            const byteCharacters = atob(this.currentPhoto.image);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'image/png' });
            
            // Crear Object URL para descarga
            const blobUrl = URL.createObjectURL(blob);
            
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = this.currentPhoto.name || `foto_${this.photosData.lot_name}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Liberar memoria
            setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
            
            this.notification.add("Imagen descargada", { type: "success" });
        } catch (err) {
            console.error("Error al descargar:", err);
            this.notification.add("Error al descargar la imagen", { type: "danger" });
        }
    }

    async shareCurrentImage() {
        if (!this.currentPhoto) return;
        
        // Convertir base64 a Blob
        const byteCharacters = atob(this.currentPhoto.image);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'image/png' });
        const file = new File([blob], this.currentPhoto.name || 'imagen.png', { type: 'image/png' });

        // Web Share API (móvil)
        if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
            try {
                await navigator.share({
                    title: `Foto - ${this.photosData.lot_name}`,
                    text: `Imagen del lote ${this.photosData.lot_name}`,
                    files: [file]
                });
                this.notification.add("Imagen compartida", { type: "success" });
            } catch (err) {
                if (err.name !== 'AbortError') {
                    this.copyImageToClipboard();
                }
            }
        } else {
            this.copyImageToClipboard();
        }
    }

    async copyImageToClipboard() {
        if (!this.currentPhoto) return;
        
        try {
            const byteCharacters = atob(this.currentPhoto.image);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'image/png' });
            
            await navigator.clipboard.write([
                new ClipboardItem({ 'image/png': blob })
            ]);
            
            this.notification.add("Imagen copiada al portapapeles", { type: "success" });
        } catch (err) {
            this.notification.add("No se pudo copiar la imagen", { type: "warning" });
        }
    }

    // === EDITOR DE DIBUJO FULLSCREEN ===

    openDrawingEditor() {
        this.state.showDrawingEditor = true;
        document.body.style.overflow = 'hidden';
        setTimeout(() => this.initDrawingCanvas(), 50);
    }

    closeDrawingEditor() {
        this.state.showDrawingEditor = false;
        document.body.style.overflow = '';
    }

    initDrawingCanvas() {
        const canvas = this.editorCanvasRef.el;
        const img = this.editorImageRef.el;
        
        if (!canvas || !img) {
            console.error('Canvas o imagen no encontrados');
            return;
        }

        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        
        const setupCanvas = () => {
            const container = canvas.parentElement;
            const containerRect = container.getBoundingClientRect();
            
            const imgRatio = img.naturalWidth / img.naturalHeight;
            const containerRatio = containerRect.width / containerRect.height;
            
            let canvasWidth, canvasHeight;
            
            if (imgRatio > containerRatio) {
                canvasWidth = containerRect.width;
                canvasHeight = containerRect.width / imgRatio;
            } else {
                canvasHeight = containerRect.height;
                canvasWidth = containerRect.height * imgRatio;
            }
            
            canvas.width = canvasWidth;
            canvas.height = canvasHeight;
            canvas.style.width = canvasWidth + 'px';
            canvas.style.height = canvasHeight + 'px';
            
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            
            this.redrawCanvas();
        };

        if (img.complete && img.naturalWidth > 0) {
            setupCanvas();
        } else {
            img.onload = setupCanvas;
        }
    }

    setColor(color) {
        this.state.brushColor = color;
    }

    setBrushSize(size) {
        this.state.brushSize = parseInt(size);
    }

    getPointerPosition(e) {
        if (!this.canvas) return { x: 0, y: 0 };
        
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        
        let clientX, clientY;
        
        if (e.touches && e.touches.length > 0) {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else {
            clientX = e.clientX;
            clientY = e.clientY;
        }
        
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY
        };
    }

    onCanvasPointerDown(e) {
        e.preventDefault();
        e.stopPropagation();
        
        this.state.isDrawing = true;
        
        const pos = this.getPointerPosition(e);
        this.currentPath = [{
            x: pos.x,
            y: pos.y,
            color: this.state.brushColor,
            size: this.state.brushSize
        }];
        
        this.ctx.beginPath();
        this.ctx.moveTo(pos.x, pos.y);
        this.ctx.strokeStyle = this.state.brushColor;
        this.ctx.lineWidth = this.state.brushSize;
        
        this.ctx.lineTo(pos.x + 0.1, pos.y + 0.1);
        this.ctx.stroke();
    }

    onCanvasPointerMove(e) {
        if (!this.state.isDrawing) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const pos = this.getPointerPosition(e);
        
        this.currentPath.push({
            x: pos.x,
            y: pos.y,
            color: this.state.brushColor,
            size: this.state.brushSize
        });
        
        this.ctx.lineTo(pos.x, pos.y);
        this.ctx.stroke();
    }

    onCanvasPointerUp(e) {
        if (!this.state.isDrawing) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        this.state.isDrawing = false;
        this.ctx.closePath();
        
        if (this.currentPath.length > 0) {
            this.drawingHistory.push([...this.currentPath]);
            this.state.canUndo = true;
        }
        this.currentPath = [];
    }

    undoLastStroke() {
        if (this.drawingHistory.length === 0) return;
        
        this.drawingHistory.pop();
        this.redrawCanvas();
        this.state.canUndo = this.drawingHistory.length > 0;
    }

    clearDrawing() {
        this.drawingHistory = [];
        if (this.ctx && this.canvas) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        this.state.canUndo = false;
    }

    redrawCanvas() {
        if (!this.ctx || !this.canvas) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        for (const path of this.drawingHistory) {
            if (path.length === 0) continue;
            
            this.ctx.beginPath();
            this.ctx.strokeStyle = path[0].color;
            this.ctx.lineWidth = path[0].size;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            this.ctx.moveTo(path[0].x, path[0].y);
            
            for (let i = 1; i < path.length; i++) {
                this.ctx.lineTo(path[i].x, path[i].y);
            }
            this.ctx.stroke();
            this.ctx.closePath();
        }
    }

    saveDrawingAndClose() {
        this.closeDrawingEditor();
        this.notification.add("Anotaciones guardadas", { type: "success" });
    }

    // === COMPRESIÓN Y SUBIDA ===

    async compressImage(file) {
        return new Promise((resolve, reject) => {
            const { maxWidth, maxHeight, quality, maxSizeKB, minQuality } = this.compressionConfig;
            
            const img = new Image();
            
            img.onload = () => {
                URL.revokeObjectURL(img.src);
                
                let { width, height } = img;
                
                if (width > maxWidth || height > maxHeight) {
                    const ratio = Math.min(maxWidth / width, maxHeight / height);
                    width = Math.round(width * ratio);
                    height = Math.round(height * ratio);
                }
                
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                
                const ctx = canvas.getContext('2d');
                
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, width, height);
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                ctx.drawImage(img, 0, 0, width, height);
                
                if (this.drawingHistory.length > 0 && this.canvas) {
                    const scaleX = width / this.canvas.width;
                    const scaleY = height / this.canvas.height;
                    
                    for (const path of this.drawingHistory) {
                        if (path.length === 0) continue;
                        
                        ctx.beginPath();
                        ctx.strokeStyle = path[0].color;
                        ctx.lineWidth = path[0].size * Math.min(scaleX, scaleY);
                        ctx.lineCap = 'round';
                        ctx.lineJoin = 'round';
                        ctx.moveTo(path[0].x * scaleX, path[0].y * scaleY);
                        
                        for (let i = 1; i < path.length; i++) {
                            ctx.lineTo(path[i].x * scaleX, path[i].y * scaleY);
                        }
                        ctx.stroke();
                        ctx.closePath();
                    }
                }
                
                const supportsWebP = canvas.toDataURL('image/webp').startsWith('data:image/webp');
                const mimeType = supportsWebP ? 'image/webp' : 'image/jpeg';
                const extension = supportsWebP ? 'webp' : 'jpg';
                
                let currentQuality = quality;
                let dataUrl = canvas.toDataURL(mimeType, currentQuality);
                let base64 = dataUrl.split(',')[1];
                let sizeKB = (base64.length * 0.75) / 1024;
                
                while (sizeKB > maxSizeKB && currentQuality > minQuality) {
                    currentQuality -= 0.1;
                    dataUrl = canvas.toDataURL(mimeType, currentQuality);
                    base64 = dataUrl.split(',')[1];
                    sizeKB = (base64.length * 0.75) / 1024;
                }
                
                if (sizeKB > maxSizeKB * 1.5) {
                    const scale = 0.7;
                    canvas.width = Math.round(width * scale);
                    canvas.height = Math.round(height * scale);
                    ctx.fillStyle = '#FFFFFF';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    dataUrl = canvas.toDataURL(mimeType, minQuality);
                    base64 = dataUrl.split(',')[1];
                    sizeKB = (base64.length * 0.75) / 1024;
                }
                
                resolve({
                    base64,
                    extension,
                    mimeType,
                    finalSizeKB: sizeKB,
                    finalQuality: currentQuality,
                    dimensions: { width: canvas.width, height: canvas.height }
                });
            };
            
            img.onerror = () => {
                URL.revokeObjectURL(img.src);
                reject(new Error('Error al cargar la imagen'));
            };
            
            img.src = URL.createObjectURL(file);
        });
    }
    
    async uploadPhoto() {
        if (!this.state.selectedFile) {
            this.notification.add("Por favor selecciona una imagen", { type: "warning" });
            return;
        }
        
        this.state.isUploading = true;
        
        try {
            const compressed = await this.compressImage(this.state.selectedFile);
            
            this.state.compressionInfo = {
                ...this.state.compressionInfo,
                compressedSize: compressed.finalSizeKB.toFixed(1) + ' KB',
                reduction: Math.round((1 - (compressed.finalSizeKB * 1024) / this.state.compressionInfo.originalSizeBytes) * 100) + '%',
            };
            
            let photoName = this.state.photoName;
            photoName = photoName.replace(/\.(jpg|jpeg|png|gif|webp|bmp)$/i, '');
            photoName = `${photoName}.${compressed.extension}`;
            
            const result = await this.orm.call(
                "stock.quant",
                "save_lot_photo",
                [],
                {
                    quant_id: this.detailId,
                    photo_name: photoName,
                    photo_data: compressed.base64,
                    sequence: 10,
                    notas: ''
                }
            );
            
            if (result.success) {
                const infoMsg = `${result.message} (${compressed.finalSizeKB.toFixed(0)} KB)`;
                this.notification.add(infoMsg, { type: "success" });
                this.props.close();
                if (this.props.onReload) {
                    await this.props.onReload();
                }
            } else {
                this.notification.add(result.error || "Error al subir foto", { type: "danger" });
            }
        } catch (error) {
            console.error("Error al subir foto:", error);
            this.notification.add("Error al procesar imagen: " + error.message, { type: "danger" });
        } finally {
            this.state.isUploading = false;
        }
    }
    
    openImageInNewTab(imageData) {
        // Ahora abre el visor fullscreen en lugar de nueva pestaña
        this.openFullscreenViewer();
    }
}

PhotoGalleryDialog.template = "inventory_visual_enhanced.PhotoGalleryDialog";
PhotoGalleryDialog.components = { Dialog };