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
  private mapWidth: number = 0;
  private mapHeight: number = 0;
  private canvasWidth: number = 1920;
  private canvasHeight: number = 1080;

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

    console.log('✓ GPU initialized');
  }

  async loadMapTextures(
    westData: Uint16Array,
    eastData: Uint16Array,
    width: number,
    height: number
  ) {
    this.mapWidth = width;
    this.mapHeight = height;

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

  createColorBuffer(provinceCount: number) {
    // Uniforms struct must be 16-byte aligned
    this.uniformsBuffer = this.device.createBuffer({
      size: 48,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    // Create color/state buffers
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

    // Initialize with default values
    const defaultPrimary = new Uint32Array(provinceCount).fill(0x5E5E5E);
    const defaultStates = new Uint32Array(provinceCount).fill(0);
    const defaultOwner = new Uint32Array(provinceCount).fill(0x5E5E5E);
    const defaultSecondary = new Uint32Array(provinceCount).fill(0);

    this.queue.writeBuffer(this.primaryColorsBuffer, 0, defaultPrimary.buffer);
    this.queue.writeBuffer(this.statesBuffer, 0, defaultStates.buffer);
    this.queue.writeBuffer(this.ownerColorsBuffer, 0, defaultOwner.buffer);
    this.queue.writeBuffer(this.secondaryColorsBuffer, 0, defaultSecondary.buffer);

    this.updateUniforms();

    console.log(`✓ Color buffers created (${provinceCount} provinces)`);
  }

  private updateUniforms() {
    const data = new ArrayBuffer(48);
    const view = new DataView(data);

    view.setUint32(0, this.mapWidth, true);           // tile_width
    view.setUint32(4, this.mapHeight, true);          // tile_height
    view.setUint32(8, 1, true);                       // enable_location_borders
    view.setUint32(12, 0, true);                      // enable_owner_borders
    view.setUint32(16, 0, true);                      // view_x
    view.setUint32(20, 0, true);                      // view_y
    view.setUint32(24, this.mapWidth * 2, true);      // view_width
    view.setUint32(28, this.mapHeight, true);         // view_height
    view.setFloat32(32, 1.0, true);                   // zoom_level
    view.setUint32(36, this.canvasWidth, true);       // surface_width
    view.setUint32(40, this.canvasHeight, true);      // surface_height

    this.queue.writeBuffer(this.uniformsBuffer, 0, data);
  }

  updateProvinceColors(colors: Uint32Array) {
    this.queue.writeBuffer(this.primaryColorsBuffer, 0, colors.buffer);
    this.queue.writeBuffer(this.ownerColorsBuffer, 0, colors.buffer);
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
        { binding: 2, visibility: GPUShaderStage.FRAGMENT, buffer: { type: 'uniform' } },
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

    console.log('✓ Render pipeline created');
  }

  configureCanvas(canvas: HTMLCanvasElement) {
    this.canvasWidth = canvas.width;
    this.canvasHeight = canvas.height;

    this.canvasContext = canvas.getContext('webgpu') as GPUCanvasContext;
    if (!this.canvasContext) {
      throw new Error('Failed to get WebGPU canvas context');
    }

    this.canvasContext.configure({
      device: this.device,
      format: navigator.gpu.getPreferredCanvasFormat(),
    });

    // Update uniforms with actual canvas size
    this.updateUniforms();
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
          clearValue: { r: 0.1, g: 0.1, b: 0.1, a: 1 },
          loadOp: 'clear',
          storeOp: 'store',
        },
      ],
    });

    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, this.bindGroup);
    pass.draw(3);
    pass.end();

    this.queue.submit([encoder.finish()]);
  }
}
