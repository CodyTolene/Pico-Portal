// ============================================================================
//  Project: Pico Portal
//  License: CC-BY-NC-4.0
//  SPDX-License-Identifier: CC-BY-NC-4.0
//  Repository: https://github.com/CodyTolene/Pico-Portal
//  Description: A script to download and extract specific folders from Git
//   repositories. This script is used to download and extract the necessary
//   files for Pico Portal MicroPython development.
// ============================================================================

import AdmZip from "adm-zip";
import { sync } from "rimraf";
import { exec } from "child_process";
import { existsSync as pathExists, mkdirSync as makePath } from "fs";
import { resolve as pathResolve, join as pathJoin } from "path";

interface Repo {
    extractFromDir?: string;
    extractToDir: string;
    url: string;
}

const repositories: readonly Repo[] = [
    {
        extractFromDir: "phew-main/phew",
        extractToDir: "./src/modules/phew",
        url: "https://github.com/pimoroni/phew/archive/refs/heads/main.zip",
    },
];

/**
 * Function to run shell commands, log the output as well.
 * 
 * @param command - The command to run
 * @returns A promise that resolves when the command is done executing
 */
function runCommand(command: string): Promise<void> {
  return new Promise((resolve, reject) => {
    exec(command, (error, stdout, stderr) => {
      if (error) {
        console.error(`Error executing command: ${command}\n${error.message}`);
        console.error(stderr);
        reject(error);
      } else {
        resolve();
      }
    });
  });
}

/**
 * Function to download and extract specific folders from repositories.
 * 
 * @param repos - The list of Git repositories to download and extract.
 */
async function extractRepositories(repos: readonly Repo[]): Promise<void> {
    for (const repo of repos) {
      const { extractToDir, extractFromDir, url } = repo;

      const fullPath = pathResolve(extractToDir);
      const zipPath = pathJoin(fullPath, "repo.zip");
      const tempExtractPath = pathResolve(extractToDir, "../temp_extract");

      if (pathExists(fullPath)) {
        sync(fullPath);
        console.log(`Cleared existing files in ${fullPath}`);
        makePath(fullPath, { recursive: true }); // Recreate the directory
      }

      console.log(`Creating directory: ${fullPath}`);
      makePath(fullPath, { recursive: true });

      console.log(`Downloading ${url}...`);
      try {
        await runCommand(`curl -L ${url} -o ${zipPath}`);

        if (!pathExists(tempExtractPath)) {
            makePath(tempExtractPath, { recursive: true });
        }

        const zip = new AdmZip(zipPath);
        zip.extractAllTo(tempExtractPath, true);
        const sourcePath = extractFromDir ? pathJoin(tempExtractPath, extractFromDir) : tempExtractPath;

        if (pathExists(sourcePath)) {
          await runCommand(`mv ${sourcePath}/* ${fullPath}/`);
          console.log(`Successfully copied assets to ${fullPath}`);
          
          sync(zipPath);
          sync(tempExtractPath);
        } else {
          console.error(`Source path ${sourcePath} does not exist!`);
        }
      } catch (e) {
        console.error(`Failed to process ${url}: ${e}`);
      }
    }

    console.log("Completed!");
}

extractRepositories(repositories);
