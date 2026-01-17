struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    let uv = vec2<f32>(f32(vertex_index >> 1u), f32(vertex_index & 1u)) * 2.0;
    let clip_position = vec4<f32>(uv * vec2<f32>(2.0, -2.0) + vec2<f32>(-1.0, 1.0), 0.0, 1.0);
    return VertexOutput(clip_position, uv);
}

struct ComputeUniforms {
    tile_width: u32,
    tile_height: u32,
    enable_location_borders: u32,
    enable_owner_borders: u32,

    view_x: u32,
    view_y: u32,
    view_width: u32,
    view_height: u32,

    zoom_level: f32,
    surface_width: u32,
    surface_height: u32,
    
    max_province_id: u32,
}

@group(0) @binding(0) var west_input_texture: texture_2d<u32>;
@group(0) @binding(1) var east_input_texture: texture_2d<u32>;
@group(0) @binding(2) var<uniform> uniforms: ComputeUniforms;
@group(0) @binding(3) var<storage, read> location_primary_colors: array<u32>;
@group(0) @binding(4) var<storage, read> location_states: array<u32>;
@group(0) @binding(5) var<storage, read> location_owner_colors: array<u32>;
@group(0) @binding(6) var<storage, read> location_secondary_colors: array<u32>;

// Fallback color for out-of-bounds province IDs
const FALLBACK_COLOR: vec3<f32> = vec3<f32>(0.678, 0.588, 0.455);

fn wrap_x(x: i32) -> i32 {
    let w = i32(uniforms.tile_width * 2u);
    return ((x % w) + w) % w;
}

fn unpack_color(value: u32) -> vec3<f32> {
    return vec3<f32>(
        f32((value >> 16u) & 0xFFu) / 255.0,
        f32((value >> 8u) & 0xFFu) / 255.0,
        f32(value & 0xFFu) / 255.0
    );
}

fn get_location_at(x: i32, y: i32) -> u32 {
    let cy = clamp(y, 0, i32(uniforms.tile_height) - 1);
    let wx = wrap_x(x);
    
    if (wx < i32(uniforms.tile_width)) {
        return textureLoad(west_input_texture, vec2<i32>(wx, cy), 0).r;
    } else {
        return textureLoad(east_input_texture, vec2<i32>(wx - i32(uniforms.tile_width), cy), 0).r;
    }
}

// Get color for a province with bounds checking
fn get_province_color(loc: u32) -> vec3<f32> {
    if (loc >= uniforms.max_province_id) {
        return FALLBACK_COLOR;
    }
    return unpack_color(location_primary_colors[loc]);
}

// Get owner color for a province with bounds checking
fn get_owner_color(loc: u32) -> u32 {
    if (loc >= uniforms.max_province_id) {
        return 0u;
    }
    return location_owner_colors[loc];
}

// Get secondary color (for occupation stripes) with bounds checking
fn get_secondary_color(loc: u32) -> u32 {
    if (loc >= uniforms.max_province_id) {
        return 0u;
    }
    return location_secondary_colors[loc];
}

// Get base color for a location (no border processing)
fn get_base_color(x: i32, y: i32) -> vec3<f32> {
    let loc = get_location_at(x, y);
    return get_province_color(loc);
}

// Check if pixel is on an owner border
fn is_owner_border(x: i32, y: i32) -> bool {
    let loc = get_location_at(x, y);
    if (loc >= uniforms.max_province_id) {
        return false;
    }
    
    let owner = get_owner_color(loc);
    
    // Check 8 neighbors
    let loc_n = get_location_at(x, y - 1);
    let loc_s = get_location_at(x, y + 1);
    let loc_w = get_location_at(x - 1, y);
    let loc_e = get_location_at(x + 1, y);
    let loc_nw = get_location_at(x - 1, y - 1);
    let loc_ne = get_location_at(x + 1, y - 1);
    let loc_sw = get_location_at(x - 1, y + 1);
    let loc_se = get_location_at(x + 1, y + 1);
    
    return (loc_n < uniforms.max_province_id && get_owner_color(loc_n) != owner) ||
           (loc_s < uniforms.max_province_id && get_owner_color(loc_s) != owner) ||
           (loc_w < uniforms.max_province_id && get_owner_color(loc_w) != owner) ||
           (loc_e < uniforms.max_province_id && get_owner_color(loc_e) != owner) ||
           (loc_nw < uniforms.max_province_id && get_owner_color(loc_nw) != owner) ||
           (loc_ne < uniforms.max_province_id && get_owner_color(loc_ne) != owner) ||
           (loc_sw < uniforms.max_province_id && get_owner_color(loc_sw) != owner) ||
           (loc_se < uniforms.max_province_id && get_owner_color(loc_se) != owner);
}

// Simple pixel color with borders and occupation stripes
fn get_pixel_color(x: i32, y: i32) -> vec3<f32> {
    let loc = get_location_at(x, y);
    var base = get_province_color(loc);
    
    // Skip borders for out-of-bounds provinces
    if (loc >= uniforms.max_province_id) {
        return base;
    }
    
    // Check for occupation stripes (secondary color)
    let secondary = get_secondary_color(loc);
    if (secondary != 0u) {
        // Create diagonal stripes for occupied territories
        let stripe_width = 3.0; // Width of each stripe in pixels (smaller = denser)
        let pattern = (f32(x) + f32(y)) / stripe_width;
        let stripe = fract(pattern);
        if (stripe > 0.4) {
            // Use occupier's color for stripe (0.4 threshold = 60% stripe coverage)
            base = unpack_color(secondary);
        }
    }
    
    let owner = get_owner_color(loc);
    
    // Check neighbors for borders
    let loc_n = get_location_at(x, y - 1);
    let loc_s = get_location_at(x, y + 1);
    let loc_w = get_location_at(x - 1, y);
    let loc_e = get_location_at(x + 1, y);
    
    // Country borders (thicker - check diagonals too)
    // Draw border if neighbor has DIFFERENT owner
    if (uniforms.enable_owner_borders != 0u) {
        let loc_nw = get_location_at(x - 1, y - 1);
        let loc_ne = get_location_at(x + 1, y - 1);
        let loc_sw = get_location_at(x - 1, y + 1);
        let loc_se = get_location_at(x + 1, y + 1);
        
        if ((loc_n < uniforms.max_province_id && get_owner_color(loc_n) != owner) ||
            (loc_s < uniforms.max_province_id && get_owner_color(loc_s) != owner) ||
            (loc_w < uniforms.max_province_id && get_owner_color(loc_w) != owner) ||
            (loc_e < uniforms.max_province_id && get_owner_color(loc_e) != owner) ||
            (loc_nw < uniforms.max_province_id && get_owner_color(loc_nw) != owner) ||
            (loc_ne < uniforms.max_province_id && get_owner_color(loc_ne) != owner) ||
            (loc_sw < uniforms.max_province_id && get_owner_color(loc_sw) != owner) ||
            (loc_se < uniforms.max_province_id && get_owner_color(loc_se) != owner)) {
            return base * 0.5;
        }
    }
    
    return base;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let px = min(u32(in.position.x), uniforms.surface_width - 1u);
    let py = min(u32(in.position.y), uniforms.surface_height - 1u);
    
    // Calculate world coordinates (floating point for subpixel precision)
    let world_x = f32(uniforms.view_x) + (f32(px) / f32(uniforms.surface_width)) * f32(uniforms.view_width);
    let world_y = f32(uniforms.view_y) + (f32(py) / f32(uniforms.surface_height)) * f32(uniforms.view_height);
    
    let x0 = i32(floor(world_x));
    let y0 = i32(floor(world_y));
    
    // Get fractional position within the map pixel
    let fx = fract(world_x);
    let fy = fract(world_y);
    
    // Check if we're at a border - only apply AA at borders
    let on_border = is_owner_border(x0, y0);
    
    if (on_border && uniforms.zoom_level < 2.0) {
        // Subpixel anti-aliasing: sample 4 corners and blend based on position
        let c00 = get_pixel_color(x0, y0);
        let c10 = get_pixel_color(x0 + 1, y0);
        let c01 = get_pixel_color(x0, y0 + 1);
        let c11 = get_pixel_color(x0 + 1, y0 + 1);
        
        // Bilinear interpolation
        let c0 = mix(c00, c10, fx);
        let c1 = mix(c01, c11, fx);
        let color = mix(c0, c1, fy);
        
        return vec4<f32>(color, 1.0);
    } else {
        // Normal pixel - no AA needed
        let color = get_pixel_color(x0, y0);
        return vec4<f32>(color, 1.0);
    }
}
