export class MapGpuContext {
  private device!: GPUDevice;
  private queue!: GPUQueue;
  private westTexture!: GPUTexture;
  private eastTexture!: GPUTexture;
  private uniformsBuffer!: GPUBuffer;
  private primaryColorsBuffer!: GPUBuffer;
  private statesBuffer!: GPUBuffer;
  private ownerColorsBuffer!: GPUBuffer;
  private secondaryColorsBuffer!: GPUBuffer;
  private shaderModule!: GPUShaderModule;
  private pipeline!: GPURenderPipeline;
  private bindGroupLayout!: GPUBindGroupLayout;
  private bindGroup!: GPUBindGroup;
  private canvasContext?: GPUCanvasContext;
  private tileWidth: number = 0;
  private tileHeight: number = 0;
  private canvasWidth: number = 1920;
  private canvasHeight: number = 1080;
  private maxProvinceId: number = 8192;

  static async create(): Promise<MapGpuContext> {
    const context = new MapGpuContext();
    await context.init();
    return context;
  }

  private async init() {
    if (!navigator.gpu) {
      throw new Error('WebGPU not supported in this browser');
    }

    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) {
      throw new Error('Failed to get GPU adapter');
    }

    this.device = await adapter.requestDevice();
    this.queue = this.device.queue;

    console.log('GPU initialized');
  }

  async loadMapTextures(
    westData: Uint16Array,
    eastData: Uint16Array,
    width: number,
    height: number
  ) {
    this.westTexture = this.device.createTexture({
      size: { width, height },
      format: 'r16uint',
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST,
    });

    this.queue.writeTexture(
      { texture: this.westTexture },
      westData.buffer,
      { bytesPerRow: width * 2 },
      { width, height }
    );

    this.eastTexture = this.device.createTexture({
      size: { width, height },
      format: 'r16uint',
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST,
    });

    this.queue.writeTexture(
      { texture: this.eastTexture },
      eastData.buffer,
      { bytesPerRow: width * 2 },
      { width, height }
    );

    console.log(`✓ Map textures uploaded (${width}x${height})`);
  }

  createUniformBuffer(tileWidth: number, tileHeight: number, maxProvinceId: number = 8192) {
    this.tileWidth = tileWidth;
    this.tileHeight = tileHeight;
    this.maxProvinceId = maxProvinceId;

    // Uniforms struct - needs 48 bytes + padding to 64
    this.uniformsBuffer = this.device.createBuffer({
      size: 64,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    console.log(`Uniform buffer created (tile: ${tileWidth}x${tileHeight}, maxProvinceId: ${maxProvinceId})`);
  }

  createColorBuffers(provinceCount: number) {
    // Create all 4 color/state buffers
    this.primaryColorsBuffer = this.device.createBuffer({
      size: provinceCount * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });

    this.statesBuffer = this.device.createBuffer({
      size: provinceCount * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });

    this.ownerColorsBuffer = this.device.createBuffer({
      size: provinceCount * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });

    this.secondaryColorsBuffer = this.device.createBuffer({
      size: provinceCount * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });

    // Initialize with default values (gray)
    const defaultColor = packColor(173, 150, 116);
    const defaultPrimary = new Uint32Array(provinceCount).fill(defaultColor);
    const defaultStates = new Uint32Array(provinceCount).fill(0);
    const defaultOwner = new Uint32Array(provinceCount).fill(defaultColor);
    const defaultSecondary = new Uint32Array(provinceCount).fill(0);

    this.queue.writeBuffer(this.primaryColorsBuffer, 0, defaultPrimary.buffer as ArrayBuffer);
    this.queue.writeBuffer(this.statesBuffer, 0, defaultStates.buffer as ArrayBuffer);
    this.queue.writeBuffer(this.ownerColorsBuffer, 0, defaultOwner.buffer as ArrayBuffer);
    this.queue.writeBuffer(this.secondaryColorsBuffer, 0, defaultSecondary.buffer as ArrayBuffer);

    console.log(`✓ Color buffers created (${provinceCount} provinces)`);
  }

  updateUniforms(viewport: {
    x: number;
    y: number;
    width: number;
    height: number;
    zoom: number;
  }) {
    const data = new ArrayBuffer(64);
    const view = new DataView(data);
    let offset = 0;

    // struct ComputeUniforms (must match WGSL)
    view.setUint32(offset, this.tileWidth, true);
    offset += 4;
    view.setUint32(offset, this.tileHeight, true);
    offset += 4;
    view.setUint32(offset, 1, true); // enable_location_borders
    offset += 4;
    view.setUint32(offset, 1, true); // enable_owner_borders
    offset += 4;
    view.setUint32(offset, Math.floor(viewport.x), true); // view_x
    offset += 4;
    view.setUint32(offset, Math.floor(viewport.y), true); // view_y
    offset += 4;
    view.setUint32(offset, Math.floor(viewport.width), true); // view_width
    offset += 4;
    view.setUint32(offset, Math.floor(viewport.height), true); // view_height
    offset += 4;
    view.setFloat32(offset, viewport.zoom, true); // zoom_level
    offset += 4;
    view.setUint32(offset, this.canvasWidth, true); // surface_width
    offset += 4;
    view.setUint32(offset, this.canvasHeight, true); // surface_height
    offset += 4;
    view.setUint32(offset, this.maxProvinceId, true); // max_province_id

    this.queue.writeBuffer(this.uniformsBuffer, 0, data);
  }

  updateProvinceColors(colors: Uint32Array) {
    this.queue.writeBuffer(this.primaryColorsBuffer, 0, colors.buffer as ArrayBuffer);
  }

  updateOwnerColors(colors: Uint32Array) {
    this.queue.writeBuffer(this.ownerColorsBuffer, 0, colors.buffer as ArrayBuffer);
  }

  updateSecondaryColors(colors: Uint32Array) {
    this.queue.writeBuffer(this.secondaryColorsBuffer, 0, colors.buffer as ArrayBuffer);
  }

  updateStates(states: Uint32Array) {
    this.queue.writeBuffer(this.statesBuffer, 0, states.buffer as ArrayBuffer);
  }

  async createRenderPipeline(canvasFormat: GPUTextureFormat) {
    const shaderCode = await fetch('/shaders/map.wgsl').then((r) => r.text());

    this.shaderModule = this.device.createShaderModule({
      code: shaderCode,
    });

    this.bindGroupLayout = this.device.createBindGroupLayout({
      entries: [
        { binding: 0, visibility: GPUShaderStage.FRAGMENT, texture: { sampleType: 'uint', viewDimension: '2d' } },
        { binding: 1, visibility: GPUShaderStage.FRAGMENT, texture: { sampleType: 'uint', viewDimension: '2d' } },
        { binding: 2, visibility: GPUShaderStage.FRAGMENT | GPUShaderStage.VERTEX, buffer: { type: 'uniform' } },
        { binding: 3, visibility: GPUShaderStage.FRAGMENT, buffer: { type: 'read-only-storage' } },
        { binding: 4, visibility: GPUShaderStage.FRAGMENT, buffer: { type: 'read-only-storage' } },
        { binding: 5, visibility: GPUShaderStage.FRAGMENT, buffer: { type: 'read-only-storage' } },
        { binding: 6, visibility: GPUShaderStage.FRAGMENT, buffer: { type: 'read-only-storage' } },
      ],
    });

    const pipelineLayout = this.device.createPipelineLayout({
      bindGroupLayouts: [this.bindGroupLayout],
    });

    this.pipeline = this.device.createRenderPipeline({
      layout: pipelineLayout,
      vertex: {
        module: this.shaderModule,
        entryPoint: 'vs_main',
      },
      fragment: {
        module: this.shaderModule,
        entryPoint: 'fs_main',
        targets: [{ format: canvasFormat }],
      },
    });

    this.bindGroup = this.device.createBindGroup({
      layout: this.bindGroupLayout,
      entries: [
        { binding: 0, resource: this.westTexture.createView() },
        { binding: 1, resource: this.eastTexture.createView() },
        { binding: 2, resource: { buffer: this.uniformsBuffer } },
        { binding: 3, resource: { buffer: this.primaryColorsBuffer } },
        { binding: 4, resource: { buffer: this.statesBuffer } },
        { binding: 5, resource: { buffer: this.ownerColorsBuffer } },
        { binding: 6, resource: { buffer: this.secondaryColorsBuffer } },
      ],
    });

    console.log('Render pipeline created');
  }

  configureCanvas(canvas: HTMLCanvasElement, width: number, height: number) {
    this.canvasWidth = width;
    this.canvasHeight = height;

    this.canvasContext = canvas.getContext('webgpu') as GPUCanvasContext;
    if (!this.canvasContext) {
      throw new Error('Failed to get WebGPU canvas context');
    }

    this.canvasContext.configure({
      device: this.device,
      format: navigator.gpu.getPreferredCanvasFormat(),
    });

    console.log(`Canvas configured: ${width}x${height} physical pixels`);
  }

  render() {
    if (!this.canvasContext) {
      throw new Error('Canvas not configured');
    }

    const texture = this.canvasContext.getCurrentTexture();
    const view = texture.createView();

    const encoder = this.device.createCommandEncoder();

    const pass = encoder.beginRenderPass({
      colorAttachments: [
        {
          view: view,
          clearValue: { r: 0.05, g: 0.05, b: 0.05, a: 1 },
          loadOp: 'clear',
          storeOp: 'store',
        },
      ],
    });

    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, this.bindGroup);
    pass.draw(3); // Draw fullscreen triangle
    pass.end();

    this.queue.submit([encoder.finish()]);
  }
}

// Helper function - pack as 0x00RRGGBB to match shader unpack_color
function packColor(r: number, g: number, b: number): number {
  return (r << 16) | (g << 8) | b;
}