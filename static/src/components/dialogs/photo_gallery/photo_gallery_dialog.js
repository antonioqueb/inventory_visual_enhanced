/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class PhotoGalleryDialog extends Component {
    setup() {
        this.photosData = this.props.photosData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        // Referencias a elementos del DOM
        this.canvasRef = useRef("drawingCanvas");
        this.previewRef = useRef("previewImage");
        
        this.state = useState({
            photoName: `Foto - ${this.photosData.lot_name}`,
            selectedFile: null,
            isUploading: false,
            showUploadForm: false,
            currentImageIndex: 0,
            compressionInfo: null,
            
            // Preview y edición
            previewUrl: null,
            showEditor: false,
            
            // Herramientas de dibujo
            isDrawing: false,
            drawingEnabled: false,
            brushColor: '#FF0000',
            brushSize: 4,
            canUndo: false,
        });

        // Configuración de compresión
        this.compressionConfig = {
            maxWidth: 1280,
            maxHeight: 1280,
            quality: 0.6,
            maxSizeKB: 200,
            minQuality: 0.3,
        };

        // Canvas y contexto
        this.canvas = null;
        this.ctx = null;
        this.drawingHistory = [];
        this.currentPath = [];
        
        // Detectar móvil
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        onMounted(() => {
            this.setupCanvas();
        });

        onWillUnmount(() => {
            if (this.state.previewUrl) {
                URL.revokeObjectURL(this.state.previewUrl);
            }
        });
    }

    setupCanvas() {
        if (this.canvasRef.el) {
            this.canvas = this.canvasRef.el;
            this.ctx = this.canvas.getContext('2d');
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
        }
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
            { color: '#FF00FF', name: 'Magenta' },
            { color: '#000000', name: 'Negro' },
            { color: '#FFFFFF', name: 'Blanco' },
        ];
    }
    
    toggleUploadForm() {
        this.state.showUploadForm = !this.state.showUploadForm;
        if (!this.state.showUploadForm) {
            this.resetEditor();
        }
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
        this.state.drawingEnabled = false;
        this.state.canUndo = false;
        this.drawingHistory = [];
        this.currentPath = [];
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
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

    // === CAPTURA DE IMAGEN ===
    
    openCamera() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.capture = 'environment'; // Cámara trasera
        input.onchange = (e) => this.handleFileSelect(e.target.files[0]);
        input.click();
    }

    openGallery() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (e) => this.handleFileSelect(e.target.files[0]);
        input.click();
    }
    
    onFileSelected(ev) {
        const file = ev.target.files[0];
        if (file) {
            this.handleFileSelect(file);
        }
    }

    handleFileSelect(file) {
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            this.notification.add("Por favor selecciona un archivo de imagen válido", { type: "warning" });
            return;
        }

        // Limpiar preview anterior
        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
        }

        this.state.selectedFile = file;
        this.state.previewUrl = URL.createObjectURL(file);
        this.state.compressionInfo = {
            originalSize: this.formatFileSize(file.size),
            originalSizeBytes: file.size,
        };
        this.state.showEditor = true;
        this.state.drawingEnabled = false;
        this.drawingHistory = [];

        // Configurar canvas cuando la imagen cargue
        setTimeout(() => this.initializeCanvasSize(), 100);
    }

    initializeCanvasSize() {
        const img = this.previewRef.el;
        if (img && this.canvas) {
            // Esperar a que la imagen cargue
            if (img.complete) {
                this.setCanvasSize(img);
            } else {
                img.onload = () => this.setCanvasSize(img);
            }
        }
    }

    setCanvasSize(img) {
        if (!this.canvas) return;
        
        const rect = img.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        
        // Redibujar historial si existe
        this.redrawCanvas();
    }
    
    onPhotoNameChange(ev) {
        this.state.photoName = ev.target.value;
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // === HERRAMIENTAS DE DIBUJO ===

    toggleDrawing() {
        this.state.drawingEnabled = !this.state.drawingEnabled;
        if (this.canvas) {
            this.canvas.style.pointerEvents = this.state.drawingEnabled ? 'auto' : 'none';
        }
    }

    setColor(color) {
        this.state.brushColor = color;
    }

    setBrushSize(size) {
        this.state.brushSize = parseInt(size);
    }

    getPointerPosition(e) {
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
        if (!this.state.drawingEnabled) return;
        
        e.preventDefault();
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
    }

    onCanvasPointerMove(e) {
        if (!this.state.isDrawing || !this.state.drawingEnabled) return;
        
        e.preventDefault();
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
        this.state.isDrawing = false;
        this.ctx.closePath();
        
        if (this.currentPath.length > 0) {
            this.drawingHistory.push([...this.currentPath]);
            this.state.canUndo = true;
        }
        this.currentPath = [];
    }

    onCanvasPointerLeave(e) {
        this.onCanvasPointerUp(e);
    }

    undoLastStroke() {
        if (this.drawingHistory.length === 0) return;
        
        this.drawingHistory.pop();
        this.redrawCanvas();
        this.state.canUndo = this.drawingHistory.length > 0;
    }

    clearDrawing() {
        this.drawingHistory = [];
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.state.canUndo = false;
    }

    redrawCanvas() {
        if (!this.ctx) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        for (const path of this.drawingHistory) {
            if (path.length === 0) continue;
            
            this.ctx.beginPath();
            this.ctx.strokeStyle = path[0].color;
            this.ctx.lineWidth = path[0].size;
            this.ctx.moveTo(path[0].x, path[0].y);
            
            for (let i = 1; i < path.length; i++) {
                this.ctx.lineTo(path[i].x, path[i].y);
            }
            this.ctx.stroke();
            this.ctx.closePath();
        }
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
                
                // Dibujar anotaciones si existen
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
        window.open(`data:image/png;base64,${imageData}`, '_blank');
    }
}

PhotoGalleryDialog.template = "inventory_visual_enhanced.PhotoGalleryDialog";
PhotoGalleryDialog.components = { Dialog };