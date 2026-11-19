const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const projectRoot = path.resolve(__dirname, '..', '..');
const threeRoot = path.join(__dirname, 'node_modules', 'three');
const htmlPath = path.join(__dirname, 'render.html');
const previewOnly = process.argv.includes('--preview');

function argumentValue(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && index + 1 < process.argv.length ? process.argv[index + 1] : fallback;
}

const modelArgument = argumentValue('--model', '000f88bb21164319ae797d315be6bc0e.glb');
const exposure = Number(argumentValue('--exposure', '0.9'));
if (!Number.isFinite(exposure) || exposure <= 0) throw new Error(`Invalid exposure: ${exposure}`);
const cameraRadius = Number(argumentValue('--radius', '4.0'));
if (!Number.isFinite(cameraRadius) || cameraRadius <= 0) {
  throw new Error(`Invalid camera radius: ${cameraRadius}`);
}
const modelCandidate = path.isAbsolute(modelArgument)
  ? modelArgument
  : path.join(projectRoot, 'data', modelArgument);
const modelPath = path.resolve(modelCandidate);
const defaultOutputName = `object_${path.basename(modelPath, path.extname(modelPath)).slice(0, 8)}`;
const outputName = argumentValue('--name', defaultOutputName);
const outputRoot = path.join(projectRoot, 'data', 'nerf_synthetic', outputName);

function mimeType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  return {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.glb': 'model/gltf-binary',
  }[extension] || 'application/octet-stream';
}

function sendFile(response, filePath) {
  fs.stat(filePath, (error, stats) => {
    if (error || !stats.isFile()) {
      response.writeHead(404);
      response.end('Not found');
      return;
    }
    response.writeHead(200, {
      'Content-Type': mimeType(filePath),
      'Content-Length': stats.size,
      'Cache-Control': 'no-store',
    });
    fs.createReadStream(filePath).pipe(response);
  });
}

function createServer() {
  return http.createServer((request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1');
    if (url.pathname === '/' || url.pathname === '/render.html') {
      sendFile(response, htmlPath);
      return;
    }
    if (url.pathname === '/model.glb') {
      sendFile(response, modelPath);
      return;
    }
    if (url.pathname.startsWith('/three/')) {
      const relative = decodeURIComponent(url.pathname.slice('/three/'.length));
      const candidate = path.resolve(threeRoot, relative);
      if (candidate === threeRoot || candidate.startsWith(threeRoot + path.sep)) {
        sendFile(response, candidate);
        return;
      }
    }
    response.writeHead(404);
    response.end('Not found');
  });
}

function trainingViews() {
  const views = [];
  const elevations = [-35, -20, -5, 10, 25, 40];
  for (const elevation of elevations) {
    for (let index = 0; index < 24; index += 1) {
      views.push({ azimuth: index * 15, elevation });
    }
  }
  return views;
}

function validationViews() {
  const views = [];
  const elevations = [-27.5, -12.5, 2.5, 17.5, 32.5];
  for (let index = 0; index < 24; index += 1) {
    views.push({
      azimuth: index * 15 + 7.5,
      elevation: elevations[index % elevations.length],
    });
  }
  return views;
}

function testViews() {
  return Array.from({ length: 40 }, (_, index) => ({
    azimuth: index * 9 + 4.5,
    elevation: 30,
  }));
}

async function renderSplit(page, split, views) {
  const splitDirectory = path.join(outputRoot, split);
  fs.mkdirSync(splitDirectory, { recursive: true });
  const frames = [];
  let cameraAngleX = null;

  for (let index = 0; index < views.length; index += 1) {
    const view = views[index];
    const result = await page.evaluate(
      ({ azimuth, elevation, radius }) => window.renderFrame(azimuth, elevation, radius),
      { ...view, radius: cameraRadius },
    );
    cameraAngleX = result.camera_angle_x;
    const baseName = `r_${String(index).padStart(3, '0')}`;
    await page.screenshot({
      path: path.join(splitDirectory, `${baseName}.png`),
      omitBackground: true,
    });
    frames.push({
      file_path: `./${split}/${baseName}`,
      rotation: 0,
      transform_matrix: result.transform_matrix,
    });
    if ((index + 1) % 20 === 0 || index + 1 === views.length) {
      console.log(`${split}: ${index + 1}/${views.length}`);
    }
  }

  const document = { camera_angle_x: cameraAngleX, frames };
  fs.writeFileSync(
    path.join(outputRoot, `transforms_${split}.json`),
    JSON.stringify(document, null, 2) + '\n',
  );
}

async function main() {
  if (!fs.existsSync(modelPath)) throw new Error(`Model not found: ${modelPath}`);
  const server = createServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
    args: [
      '--enable-webgl',
      '--ignore-gpu-blocklist',
      '--enable-unsafe-swiftshader',
      '--use-angle=swiftshader',
    ],
  });

  try {
    const page = await browser.newPage({ viewport: { width: 512, height: 512 } });
    page.on('console', (message) => console.log(`browser: ${message.text()}`));
    page.on('pageerror', (error) => console.error(`browser error: ${error.message}`));
    await page.goto(`http://127.0.0.1:${port}/render.html?exposure=${encodeURIComponent(exposure)}`, { waitUntil: 'networkidle' });
    await page.evaluate(() => window.modelReady);
    const modelInfo = await page.evaluate(() => window.modelInfo);
    console.log(`model info: ${JSON.stringify(modelInfo)}`);

    if (previewOnly) {
      fs.mkdirSync(path.join(outputRoot, 'preview'), { recursive: true });
      const result = await page.evaluate(
        (radius) => window.renderFrame(45, 20, radius),
        cameraRadius,
      );
      await page.screenshot({
        path: path.join(outputRoot, 'preview', 'preview.png'),
        omitBackground: true,
      });
      fs.writeFileSync(
        path.join(outputRoot, 'preview', 'preview.json'),
        JSON.stringify(result, null, 2) + '\n',
      );
      console.log(`preview: ${path.join(outputRoot, 'preview', 'preview.png')}`);
      return;
    }

    fs.mkdirSync(outputRoot, { recursive: true });
    await renderSplit(page, 'train', trainingViews());
    await renderSplit(page, 'val', validationViews());
    await renderSplit(page, 'test', testViews());
    fs.writeFileSync(
      path.join(outputRoot, 'dataset_info.json'),
      JSON.stringify({
        source_model: path.relative(projectRoot, modelPath).replaceAll('\\', '/'),
        image_size: [512, 512],
        camera_radius: cameraRadius,
        camera_fov_degrees: 50,
        exposure,
        train_images: 144,
        val_images: 24,
        test_images: 40,
        model_info: modelInfo,
      }, null, 2) + '\n',
    );
    console.log(`done: ${outputRoot}`);
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
