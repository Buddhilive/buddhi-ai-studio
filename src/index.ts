import { app, BrowserWindow } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';


// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

let nextProcess: ChildProcess | null = null;
const NEXT_PORT = 3434;
const NEXT_URL = `http://localhost:${NEXT_PORT}`;

const waitForServer = async (url: string, retries = 30, interval = 1000): Promise<void> => {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url);
      if (response.ok || response.status === 404) {
        return; // Server is up
      }
    } catch (err) {
      // Connection refused or socket hangup, keep trying
    }
    // Wait before next retry
    await new Promise(resolve => setTimeout(resolve, interval));
  }
  throw new Error(`Server at ${url} did not start after ${retries} seconds.`);
};

const startNextJsServer = async () => {
  const isDev = !app.isPackaged;
  
  if (isDev) {
    // In development mode, spawn `pnpm run dev` from the core directory
    // app.getAppPath() points to .webpack/main under Forge, so use process.cwd() for the project root
    const coreDir = path.resolve(process.cwd(), 'core');
    nextProcess = spawn(process.platform === 'win32' ? 'pnpm.cmd' : 'pnpm', ['run', 'dev'], {
      cwd: coreDir,
      shell: true,
      stdio: 'inherit',
    });
  } else {
    // In packaged app, next.js standalone server should be launched
    // Assume `core/.next/standalone/server.js` was packaged and included in resources.
    const standaloneDir = path.join(process.resourcesPath, 'core', '.next', 'standalone');
    nextProcess = spawn('node', ['server.js'], {
      cwd: standaloneDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        PORT: NEXT_PORT.toString(),
        NODE_ENV: 'production'
      }
    });
  }

  // Poll until Next.js is ready
  await waitForServer(NEXT_URL);
};

const createWindow = (): void => {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    height: 720,
    width: 1280,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Load the Next.js app URL
  mainWindow.loadURL(NEXT_URL);

  // Open the DevTools.
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }
};

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
app.on('ready', async () => {
  try {
    await startNextJsServer();
    createWindow();
  } catch (error) {
    console.error('Failed to start Next.js application:', error);
    app.quit();
  }
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  // Ensure Next.js child process is killed on exit
  if (nextProcess) {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', nextProcess.pid!.toString(), '/f', '/t']);
    } else {
      nextProcess.kill();
    }
  }
});
