import bpy
import bmesh
import mathutils
import numpy as np
from mathutils import Vector

bl_info = {
    "name": "Retro Console Lite",
    "author": "Tarkan Karakus",
    "version": (1, 0, 1),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Retro Console",
    "description": "Simple Game Boy Color texture conversion",
    "category": "Material",
}

# Fast color reduction using numpy vectorization
def fast_color_reduce(pixels, colors_per_channel):
    """Super fast color reduction using numpy"""
    pixels_array = np.array(pixels, dtype=np.float32)
    
    # Separate RGB and Alpha
    rgb = pixels_array[::4], pixels_array[1::4], pixels_array[2::4]
    alpha = pixels_array[3::4]
    
    # Fast quantization
    step = 1.0 / (colors_per_channel - 1)
    quantized_rgb = []
    
    for channel in rgb:
        quantized = np.round(channel / step) * step
        quantized = np.clip(quantized, 0.0, 1.0)
        quantized_rgb.append(quantized)
    
    # Rebuild pixel array
    result = np.empty(len(pixels), dtype=np.float32)
    result[::4] = quantized_rgb[0]
    result[1::4] = quantized_rgb[1] 
    result[2::4] = quantized_rgb[2]
    result[3::4] = alpha
    
    return result.tolist()

def fast_dither(pixels, width, height, colors_per_channel):
    """Fast Floyd-Steinberg dithering optimized for speed"""
    # Convert to numpy for speed
    img = np.array(pixels).reshape(height, width, 4)
    step = 1.0 / (colors_per_channel - 1)
    
    # Only process RGB channels
    for y in range(height - 1):  # Skip last row for speed
        for x in range(width - 1):  # Skip last column for speed
            for c in range(3):  # RGB only
                old_val = img[y, x, c]
                new_val = round(old_val / step) * step
                img[y, x, c] = new_val
                
                error = old_val - new_val
                
                # Simplified error diffusion (faster)
                if x + 1 < width:
                    img[y, x + 1, c] += error * 0.4
                if y + 1 < height:
                    img[y + 1, x, c] += error * 0.4
                if y + 1 < height and x + 1 < width:
                    img[y + 1, x + 1, c] += error * 0.2
    
    return np.clip(img, 0, 1).flatten().tolist()

def fast_resize_nearest(pixels, old_w, old_h, new_w, new_h):
    """Optimized nearest neighbor resize"""
    if old_w == new_w and old_h == new_h:
        return pixels
    
    # Use numpy for speed
    old_img = np.array(pixels).reshape(old_h, old_w, 4)
    
    # Calculate ratios
    x_ratio = old_w / new_w
    y_ratio = old_h / new_h
    
    # Vectorized resize
    new_img = np.zeros((new_h, new_w, 4), dtype=np.float32)
    
    for y in range(new_h):
        for x in range(new_w):
            # Fixed bounds checking
            old_x = min(int(x * x_ratio), old_w - 1)
            old_y = min(int(y * y_ratio), old_h - 1)
            new_img[y, x] = old_img[old_y, old_x]
    
    return new_img.flatten().tolist()

def setup_retro_bsdf_settings(material):
    """Set up Principled BSDF for retro/diffuse look"""
    if not material.node_tree:
        return
        
    nodes = material.node_tree.nodes
    principled = None
    
    # Find Principled BSDF
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled = node
            break
    
    if not principled:
        return
    
    # Set retro-appropriate values
    settings = {
        'Metallic': 0.0,        # Non-metallic
        'Specular': 0.0,        # No specular reflection
        'Roughness': 1.0,       # Fully matte
        'Subsurface': 0.0,      # No subsurface scattering
        'Transmission': 0.0,    # No transmission
        'Sheen': 0.0,          # No sheen
        'Clearcoat': 0.0,      # No clearcoat
        'Emission Strength': 0.0,  # No emission
        'Alpha': 1.0,          # Fully opaque
    }
    
    # Apply settings to available inputs
    for input_name, value in settings.items():
        if input_name in principled.inputs:
            principled.inputs[input_name].default_value = value
    
    # Handle emission color (set to black)
    if 'Emission Color' in principled.inputs:
        principled.inputs['Emission Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    elif 'Emission' in principled.inputs:
        principled.inputs['Emission'].default_value = (0.0, 0.0, 0.0, 1.0)

def get_original_image_name(image_name):
    """Get the original image name from a processed image name"""
    # Remove console suffix
    base_name = image_name
    if base_name.endswith('_gbc'):
        base_name = base_name[:-4]
    return base_name

def create_backup_image(original_image):
    """Create a backup of the original image"""
    try:
        base_name = get_original_image_name(original_image.name)
        backup_name = f"{base_name}_ORIGINAL_BACKUP"
        
        # Check if backup already exists
        if backup_name in bpy.data.images:
            return bpy.data.images[backup_name]
        
        # Create backup
        backup_image = original_image.copy()
        backup_image.name = backup_name
        backup_image.use_fake_user = True  # Prevent deletion
        
        print(f"Created backup: {backup_name}")
        return backup_image
        
    except Exception as e:
        print(f"Error creating backup for {original_image.name}: {e}")
        return None

class GBC_OT_Convert(bpy.types.Operator):
    """Convert textures to Game Boy Color style"""
    bl_idname = "gbc.convert"
    bl_label = "Convert to Game Boy Color"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        import time
        start_time = time.time()
        
        # Get selected objects with materials
        objects_with_materials = []
        material_count = 0
        
        try:
            if not hasattr(context, 'selected_objects') or not context.selected_objects:
                self.report({'WARNING'}, "No objects selected")
                return {'CANCELLED'}
            
            for obj in context.selected_objects:
                if not hasattr(obj, 'type') or obj.type != 'MESH':
                    continue
                    
                if not hasattr(obj, 'data') or not obj.data:
                    continue
                    
                if not hasattr(obj.data, 'materials') or not obj.data.materials:
                    continue
                    
                has_valid_materials = False
                for mat in obj.data.materials:
                    if mat and hasattr(mat, 'use_nodes') and mat.use_nodes and hasattr(mat, 'node_tree') and mat.node_tree:
                        has_valid_materials = True
                        material_count += 1
                
                if has_valid_materials:
                    objects_with_materials.append(obj)
            
            if not objects_with_materials:
                self.report({'WARNING'}, "Select objects with materials that have nodes enabled")
                return {'CANCELLED'}
        
        except Exception as e:
            print(f"Error getting selected objects: {e}")
            self.report({'ERROR'}, f"Error accessing selected objects: {str(e)}")
            return {'CANCELLED'}
        
        converted_count = 0
        
        try:
            for obj in objects_with_materials:
                for material in obj.data.materials:
                    if material and hasattr(material, 'use_nodes') and material.use_nodes:
                        if hasattr(material, 'node_tree') and material.node_tree:
                            if self.convert_material(material):
                                converted_count += 1
        except Exception as e:
            print(f"Error converting materials: {e}")
            self.report({'ERROR'}, f"Error during conversion: {str(e)}")
            return {'CANCELLED'}
        
        elapsed_time = time.time() - start_time
        self.report({'INFO'}, f"Converted {converted_count} materials to Game Boy Color style in {elapsed_time:.1f}s")
        return {'FINISHED'}
    
    def convert_material(self, material):
        """Convert material to Game Boy Color style"""
        nodes = material.node_tree.nodes
        
        # Find image texture nodes
        converted = False
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                # Ensure image has pixels loaded
                if not node.image.pixels:
                    # Try to load/generate pixels if they don't exist
                    if node.image.source == 'FILE':
                        try:
                            node.image.reload()
                        except:
                            continue
                    else:
                        continue
                
                # Create backup before processing
                backup_image = create_backup_image(node.image)
                
                # Process image
                new_image = self.process_image(node.image)
                if new_image:
                    node.image = new_image
                    node.interpolation = 'Closest'  # Pixel perfect
                    converted = True
        
        if converted:
            # Set up retro BSDF settings
            setup_retro_bsdf_settings(material)
        
        return converted
    
    def process_image(self, image):
        """Process image to Game Boy Color style"""
        try:
            # Get base name for the image
            base_name = get_original_image_name(image.name)
            
            # Use the current image as source (should be original or backup)
            source_image = image
            
            # Check if we have a backup to use instead
            backup_name = f"{base_name}_ORIGINAL_BACKUP"
            if backup_name in bpy.data.images:
                source_image = bpy.data.images[backup_name]
                print(f"Using backup image: {backup_name}")
            
            width, height = source_image.size
            
            # Check pixel data
            if len(source_image.pixels) == 0:
                print(f"No pixel data for image: {source_image.name}")
                return None
                
            pixels = list(source_image.pixels)    
                        
            # Ensure we have the right number of pixels (RGBA)
            expected_pixels = width * height * 4
            if len(pixels) != expected_pixels:
                print(f"Pixel count mismatch for {image.name}: got {len(pixels)}, expected {expected_pixels}")
                return None
            
            # Game Boy Color settings (fixed)
            target_size = 64
            colors = 4
            use_dithering = True
            
            # Resize first
            if width != target_size or height != target_size:
                pixels = fast_resize_nearest(pixels, width, height, target_size, target_size)
            
            # Apply color reduction with dithering
            if use_dithering:
                pixels = fast_dither(pixels, target_size, target_size, colors)
            else:
                pixels = fast_color_reduce(pixels, colors)
            
            # Apply Game Boy Color saturated look
            pixels = self.apply_gbc_color_shift(pixels)
            
            # Create new image
            new_name = f"{base_name}_gbc"
            
            # Remove existing image with same name
            if new_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[new_name])
            
            # Create new image
            new_image = bpy.data.images.new(
                new_name, 
                width=target_size, 
                height=target_size,
                alpha=True
            )
            
            # Ensure pixels are valid before assignment
            if len(pixels) == target_size * target_size * 4:
                new_image.pixels = pixels
                new_image.pack()
                
                # Force update
                new_image.update()
                print(f"Created processed image: {new_name}")
                return new_image
            else:
                print(f"Invalid pixel count after processing: {len(pixels)}")
                bpy.data.images.remove(new_image)
                return None
            
        except Exception as e:
            print(f"Error processing {image.name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def apply_gbc_color_shift(self, pixels):
        """Apply Game Boy Color saturated look"""
        for i in range(0, len(pixels), 4):
            for c in range(3):
                val = pixels[i+c]
                # Heavy saturation boost
                if val > 0.5:
                    pixels[i+c] = min(1.0, val * 1.4)
                else:
                    pixels[i+c] = val * 0.6
        return pixels

class GBC_OT_Reset(bpy.types.Operator):
    """Reset textures to original state"""
    bl_idname = "gbc.reset"
    bl_label = "Reset to Original"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        reset_count = 0
        
        try:
            for obj in context.selected_objects:
                if obj.type != 'MESH' or not obj.data.materials:
                    continue
                    
                for material in obj.data.materials:
                    if not material or not material.node_tree:
                        continue
                        
                    for node in material.node_tree.nodes:
                        if node.type == 'TEX_IMAGE' and node.image:
                            current_image = node.image
                            base_name = get_original_image_name(current_image.name)
                            
                            # Look for backup image
                            backup_name = f"{base_name}_ORIGINAL_BACKUP"
                            
                            if backup_name in bpy.data.images:
                                # Get backup image
                                backup_image = bpy.data.images[backup_name]
                                print(f"Found backup image: {backup_name}")
                                
                                # Create a working copy from backup
                                restored_image = backup_image.copy()
                                restored_image.name = base_name
                                
                                # Update node to use restored image
                                old_image = node.image
                                node.image = restored_image
                                
                                # Reset interpolation
                                node.interpolation = 'Linear'
                                
                                # Remove the old processed image if it's different from backup
                                if old_image != backup_image and old_image.name != backup_name:
                                    try:
                                        bpy.data.images.remove(old_image)
                                        print(f"Removed old processed image: {old_image.name}")
                                    except:
                                        pass
                                
                                reset_count += 1
                                print(f"Reset texture: {base_name}")
                            else:
                                print(f"No backup found for: {current_image.name}")
        
        except Exception as e:
            print(f"Reset error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error resetting: {str(e)}")
            return {'CANCELLED'}
        
        if reset_count > 0:
            self.report({'INFO'}, f"Reset {reset_count} textures to original")
        else:
            self.report({'WARNING'}, "No textures to reset found. Make sure you've converted textures first!")
        return {'FINISHED'}

class GBC_PT_MainPanel(bpy.types.Panel):
    """Game Boy Color converter panel"""
    bl_label = "Game Boy Color Converter"
    bl_idname = "GBC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Retro Console"
    
    def draw(self, context):
        layout = self.layout
        
        try:
            # Info box
            box = layout.box()
            box.label(text="Game Boy Color Style", icon='OBJECT_DATA')
            col = box.column(align=True)
            col.scale_y = 0.8
            col.label(text="• 64x64 pixel resolution")
            col.label(text="• 4 colors per channel")
            col.label(text="• Floyd-Steinberg dithering")
            col.label(text="• Saturated color palette")
            
            # Count materials for button display
            material_count = 0
            try:
                if hasattr(context, 'selected_objects') and context.selected_objects:
                    for obj in context.selected_objects:
                        if hasattr(obj, 'type') and obj.type == 'MESH':
                            if hasattr(obj, 'data') and obj.data and hasattr(obj.data, 'materials'):
                                for mat in obj.data.materials:
                                    if mat and hasattr(mat, 'use_nodes') and mat.use_nodes:
                                        if hasattr(mat, 'node_tree') and mat.node_tree:
                                            material_count += 1
            except Exception as e:
                print(f"Error counting materials: {e}")
                material_count = 0
                
            # Main convert button
            layout.separator()
            col = layout.column()
            col.scale_y = 2.5
            col.operator("gbc.convert", text="CONVERT TO GAME BOY COLOR", icon='MATERIAL')

            # Reset button
            layout.separator()
            col = layout.column()
            col.scale_y = 1.5
            col.operator("gbc.reset", text="RESET TO ORIGINAL", icon='RECOVER_LAST')
            
            # Instructions
            layout.separator()
            box = layout.box()
            box.label(text="Instructions:", icon='INFO')
            col = box.column(align=True)
            col.scale_y = 0.8
            col.label(text="1. Select objects with textures")
            col.label(text="2. Click CONVERT to apply Game Boy Color style")
            col.label(text="3. Use RESET to restore originals")
            
            # Status display
            if material_count > 0:
                box = layout.box()
                box.label(text=f"Ready: {material_count} materials found", icon='CHECKMARK')
            else:
                box = layout.box()
                box.label(text="Select objects with materials first", icon='ERROR')
        
        except Exception as e:
            # Error handling for panel
            error_box = layout.box()
            error_box.label(text="Panel Error", icon='ERROR')
            error_box.label(text=str(e))
            print(f"Panel error: {e}")

def register():
    """Register addon classes"""
    # Register classes
    bpy.utils.register_class(GBC_OT_Convert)
    bpy.utils.register_class(GBC_OT_Reset)
    bpy.utils.register_class(GBC_PT_MainPanel)
    
    print("Game Boy Color Lite addon registered successfully")

def unregister():
    """Unregister addon classes"""
    # Unregister classes
    bpy.utils.unregister_class(GBC_PT_MainPanel)
    bpy.utils.unregister_class(GBC_OT_Reset)
    bpy.utils.unregister_class(GBC_OT_Convert)
    
    print("Game Boy Color Lite addon unregistered")