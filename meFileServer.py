#!/usr/bin/env python3

# 咩FileServer
# zyyme 20260419

import argparse
import datetime as dt
import getpass
import html
import json
import mimetypes
import os
import secrets
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse


SIDECAR_SUFFIX = ".meFileServer.json"
UPLOAD_READ_CHUNK = 64 * 1024
PROGRESS_FLUSH_BYTES = 1024 * 1024
DOWNLOAD_CHUNK = 1024 * 1024
SESSION_COOKIE_NAME = "session"
SESSION_TTL_SECONDS = 12 * 60 * 60

HOME_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>咩FileServer</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
      --bg: #eef7ff;
      --card: rgba(255, 255, 255, 0.94);
      --line: #c8dceb;
      --ink: #12324a;
      --muted: #567189;
      --accent: #1f89e5;
      --accent-2: #dcefff;
      --danger: #b42318;
      --shadow: 0 18px 42px rgba(18, 50, 74, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(111, 187, 255, 0.22), transparent 28%),
        radial-gradient(circle at top right, rgba(58, 145, 224, 0.14), transparent 24%),
        linear-gradient(180deg, #eaf5ff 0%, var(--bg) 45%, #edf7ff 100%);
    }
    main {
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }
    .panel {
      background: var(--card);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(200, 220, 238, 0.9);
      border-radius: 22px;
      padding: 20px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }
    .hero {
      display: grid;
      gap: 10px;
      align-items: start;
    }
    .hero h1 {
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 2.6rem);
      letter-spacing: 0.02em;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    code {
      font-family: Consolas, "Courier New", monospace;
      background: #e9f4ff;
      padding: 2px 6px;
      border-radius: 8px;
      word-break: break-all;
    }
    .grid {
      display: grid;
      gap: 18px;
      grid-template-columns: 1fr;
    }
    h2 {
      margin: 0 0 10px;
      font-size: 1.22rem;
    }
    p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    .toolbar, .row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 14px;
    }
    input[type="file"] {
      max-width: 100%;
      min-width: min(100%, 260px);
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: white;
    }
    button, .link-button {
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
      transition: transform 120ms ease, filter 120ms ease, opacity 120ms ease;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    button:hover, .link-button:hover {
      filter: brightness(1.04);
      transform: translateY(-1px);
    }
    button.secondary {
      background: #4878a8;
    }
    button.light {
      background: #e7f2ff;
      color: #1f4d76;
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }
    .hint {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      background: var(--accent-2);
      color: #29557d;
      font-size: 0.94rem;
    }
    .upload-target-box {
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.8);
      align-items: center;
    }
    .upload-target-label {
      color: var(--muted);
      font-size: 0.94rem;
      font-weight: 600;
    }
    .status {
      margin-top: 12px;
      min-height: 1.5em;
      color: var(--muted);
      font-size: 0.96rem;
      word-break: break-word;
    }
    .status.error {
      color: var(--danger);
      font-weight: 600;
    }
    .progress-group {
      margin-top: 14px;
      display: grid;
      gap: 10px;
    }
    .progress-block {
      display: grid;
      gap: 6px;
    }
    .progress-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      font-size: 0.94rem;
    }
    progress {
      width: 100%;
      height: 18px;
      border-radius: 999px;
      overflow: hidden;
    }
    .tree-browser {
      margin-top: 14px;
      overflow-x: auto;
      padding-bottom: 6px;
    }
    .tree-root {
      display: grid;
      gap: 10px;
      min-width: 100%;
      width: max-content;
    }
    details.tree-dir {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.75);
      overflow: hidden;
      min-width: max-content;
    }
    details.tree-dir > summary {
      list-style: none;
      cursor: pointer;
      padding: 12px 14px;
    }
    details.tree-dir > summary::-webkit-details-marker {
      display: none;
    }
    .tree-summary {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      flex-wrap: nowrap;
      min-width: max-content;
    }
    .tree-title {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      font-weight: 700;
    }
    .badge {
      padding: 3px 8px;
      border-radius: 999px;
      background: #edf5ff;
      color: #4f7194;
      font-size: 0.85rem;
      font-weight: 600;
    }
    .tree-actions {
      display: flex;
      gap: 8px;
      flex-wrap: nowrap;
      align-items: center;
    }
    .tree-actions button {
      white-space: nowrap;
    }
    .tree-children {
      padding: 0 12px 12px 26px;
      display: grid;
      gap: 10px;
    }
    .tree-file {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: nowrap;
      background: rgba(255, 255, 255, 0.82);
      min-width: max-content;
    }
    .tree-file a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
      white-space: nowrap;
    }
    .tree-file a:hover {
      text-decoration: underline;
    }
    .meta {
      color: var(--muted);
      font-size: 0.9rem;
    }
    .empty {
      margin-top: 12px;
      color: var(--muted);
    }
    .mono {
      font-family: Consolas, "Courier New", monospace;
      white-space: nowrap;
    }
    @media (max-width: 640px) {
      main {
        padding: 18px 12px 28px;
      }
      .panel {
        border-radius: 18px;
        padding: 16px;
      }
      .tree-children {
        padding-left: 16px;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="panel hero">
      <h1>咩FileServer</h1>
      <p>当前共享根目录：<code>__ROOT__</code></p>
      <p>单文件简易文件服务器 支持文件目录断点续传上传下载</p>
      <p>哔哩哔哩：<a href="https://space.bilibili.com/9992930" target="_blank">郑羊羊</a> | 项目开源：<a href="https://github.com/zanjie1999/meFileServer" target="_blank">GitHub</a></p>
    </section>

    <div class="grid">
      <section class="panel">
        <h2>上传</h2>
        <p>已存在目录会自动合并，已存在文件会跳过</p>
        <div class="row">
          <input id="single-file-input" type="file" multiple hidden>
          <button id="upload-file-btn" type="button">上传文件</button>
          <button id="upload-folder-btn" type="button" class="secondary">上传文件夹</button>
        </div>
        <div class="row upload-target-box">
          <span class="upload-target-label">当前上传到：</span>
          <code id="upload-target-path">/</code>
          <button id="reset-upload-target-btn" type="button" class="light">切回根目录</button>
        </div>
        <div class="hint">文件夹上传和下载依赖Chromium的目录访问API，建议使用Google Chrome浏览器或者Microsoft Edge浏览器</div>
        <div id="status" class="status"></div>
        <div class="progress-group">
          <div class="progress-block">
            <div class="progress-head">
              <strong>当前文件</strong>
              <span id="current-progress-text" class="meta">尚未开始</span>
            </div>
            <progress id="current-progress" value="0" max="1"></progress>
          </div>
          <div class="progress-block">
            <div class="progress-head">
              <strong>整体进度</strong>
              <span id="task-progress-text" class="meta">暂无任务</span>
            </div>
            <progress id="task-progress" value="0" max="1"></progress>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2>下载</h2>
        <p>点击文件名可以直接下载，点击目录上的“上传到这”可以切换上传目录</p>
        <div id="tree-empty" class="empty" hidden>目录为空</div>
        <div class="tree-browser">
          <div id="tree-root" class="tree-root"></div>
        </div>
      </section>
    </div>
  </main>

  <script>
    const chunkSize = 8 * 1024 * 1024;

    const singleFileInput = document.getElementById("single-file-input");
    const uploadFileButton = document.getElementById("upload-file-btn");
    const uploadFolderButton = document.getElementById("upload-folder-btn");
    const resetUploadTargetButton = document.getElementById("reset-upload-target-btn");
    const uploadTargetPathNode = document.getElementById("upload-target-path");
    const statusNode = document.getElementById("status");
    const currentProgressNode = document.getElementById("current-progress");
    const currentProgressTextNode = document.getElementById("current-progress-text");
    const taskProgressNode = document.getElementById("task-progress");
    const taskProgressTextNode = document.getElementById("task-progress-text");
    const treeRootNode = document.getElementById("tree-root");
    const treeEmptyNode = document.getElementById("tree-empty");

    let latestTree = null;
    let busy = false;
    let currentUploadPath = "";
    const expandedDirectoryPaths = new Set();

    function formatBytes(value) {
      if (!Number.isFinite(value) || value <= 0) {
        return "0 B";
      }
      const units = ["B", "KB", "MB", "GB", "TB"];
      let size = value;
      let unitIndex = 0;
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
      }
      return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
    }

    function formatDate(value) {
      if (!value) {
        return "-";
      }
      return new Date(value).toLocaleString("zh-CN");
    }

    function setStatus(message, isError = false) {
      statusNode.textContent = message;
      statusNode.classList.toggle("error", isError);
    }

    function joinUploadPath(basePath, relativePath) {
      return basePath ? `${basePath}/${relativePath}` : relativePath;
    }

    function updateUploadTargetView() {
      uploadTargetPathNode.textContent = currentUploadPath || "/";
      resetUploadTargetButton.disabled = busy || !currentUploadPath;
    }

    function setUploadTarget(path) {
      currentUploadPath = path || "";
      updateUploadTargetView();
      if (latestTree) {
        renderTree(latestTree);
      }
      setStatus("上传目录切换成功");
    }

    function updateProgressBar(node, value, total) {
      if (total > 0) {
        node.max = total;
        node.value = Math.min(value, total);
      } else {
        node.max = 1;
        node.value = value > 0 ? 1 : 0;
      }
    }

    function setCurrentProgress(done, total, label = "尚未开始") {
      updateProgressBar(currentProgressNode, done, total);
      const percent = total > 0 ? ((done / total) * 100).toFixed(1) : (done > 0 ? "100.0" : "0.0");
      currentProgressTextNode.textContent = `${label} | ${percent}% | ${formatBytes(done)} / ${formatBytes(total)}`;
    }

    function setTaskProgress(doneBytes, totalBytes, completedFiles, skippedFiles, totalFiles) {
      const fallbackTotal = totalBytes > 0 ? totalBytes : Math.max(totalFiles, 1);
      const fallbackDone = totalBytes > 0 ? doneBytes : completedFiles;
      updateProgressBar(taskProgressNode, fallbackDone, fallbackTotal);
      const percent = fallbackTotal > 0 ? ((fallbackDone / fallbackTotal) * 100).toFixed(1) : "0.0";
      taskProgressTextNode.textContent = `已完成 ${completedFiles} / ${totalFiles} 个文件，已跳过 ${skippedFiles} 个，累计处理 ${formatBytes(doneBytes)} / ${formatBytes(totalBytes)}，进度 ${percent}%`;
    }

    function resetProgress() {
      setCurrentProgress(0, 0, "尚未开始");
      setTaskProgress(0, 0, 0, 0, 0);
    }

    function setBusyState(nextBusy) {
      busy = nextBusy;
      singleFileInput.disabled = nextBusy;
      uploadFileButton.disabled = nextBusy;
      uploadFolderButton.disabled = nextBusy;
      updateUploadTargetView();
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      const contentType = response.headers.get("content-type") || "";
      let payload = {};
      if (contentType.includes("application/json")) {
        payload = await response.json();
      } else {
        const text = await response.text();
        payload = text ? { message: text } : {};
      }
      return { response, payload };
    }

    function relativeFromBase(fullPath, basePath) {
      if (!basePath) {
        return fullPath;
      }
      if (fullPath === basePath) {
        return "";
      }
      return fullPath.slice(basePath.length + 1);
    }

    function collectTreeEntries(node, basePath) {
      const directories = [];
      const files = [];

      function walk(current) {
        if (current.type === "目录") {
          const relativePath = relativeFromBase(current.path, basePath);
          if (relativePath) {
            directories.push(relativePath);
          }
          for (const child of current.children || []) {
            walk(child);
          }
          return;
        }
        files.push({
          path: current.path,
          relativePath: relativeFromBase(current.path, basePath),
          size: current.size,
          download_url: current.download_url,
        });
      }

      walk(node);
      return { directories, files };
    }

    function createMetaText(parts) {
      return parts.filter(Boolean).join(" | ");
    }

    function renderFileNode(node) {
      const wrapper = document.createElement("div");
      wrapper.className = "tree-file";

      const link = document.createElement("a");
      link.href = node.download_url;
      link.textContent = node.name;

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = createMetaText([
        formatBytes(node.size),
        formatDate(node.mtime),
      ]);

      wrapper.appendChild(link);
      wrapper.appendChild(meta);
      return wrapper;
    }

    function renderDirectoryNode(node, isRoot = false) {
      const details = document.createElement("details");
      details.className = "tree-dir";
      details.open = isRoot || expandedDirectoryPaths.has(node.path);
      details.addEventListener("toggle", () => {
        if (isRoot) {
          return;
        }
        if (details.open) {
          expandedDirectoryPaths.add(node.path);
        } else {
          expandedDirectoryPaths.delete(node.path);
        }
      });

      const summary = document.createElement("summary");
      const summaryRow = document.createElement("div");
      summaryRow.className = "tree-summary";

      const titleWrap = document.createElement("div");
      titleWrap.className = "tree-title";

      const title = document.createElement("span");
      title.textContent = isRoot ? `根目录：${node.name}` : node.name;

      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = `${node.children.length} 项`;

      titleWrap.appendChild(title);
      titleWrap.appendChild(badge);

      const actions = document.createElement("div");
      actions.className = "tree-actions";

      if (!isRoot) {
        const uploadButton = document.createElement("button");
        uploadButton.type = "button";
        uploadButton.className = node.path === currentUploadPath ? "secondary" : "light";
        uploadButton.textContent = node.path === currentUploadPath ? "当前选择" : "上传到这";
        uploadButton.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          setUploadTarget(node.path);
        });
        actions.appendChild(uploadButton);
      }

      const downloadButton = document.createElement("button");
      downloadButton.type = "button";
      downloadButton.className = "light";
      downloadButton.textContent = isRoot ? "下载整个根目录" : "下载目录";
      downloadButton.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        await downloadDirectoryNode(node);
      });

      actions.appendChild(downloadButton);

      summaryRow.appendChild(titleWrap);
      summaryRow.appendChild(actions);
      summary.appendChild(summaryRow);
      details.appendChild(summary);

      const childrenWrap = document.createElement("div");
      childrenWrap.className = "tree-children";
      if (!node.children.length) {
        const empty = document.createElement("div");
        empty.className = "meta";
        empty.textContent = "目录为空";
        childrenWrap.appendChild(empty);
      } else {
        for (const child of node.children) {
          if (child.type === "目录") {
            childrenWrap.appendChild(renderDirectoryNode(child));
          } else {
            childrenWrap.appendChild(renderFileNode(child));
          }
        }
      }
      details.appendChild(childrenWrap);
      return details;
    }

    function renderTree(tree) {
      treeRootNode.innerHTML = "";
      latestTree = tree;
      const hasItems = !!tree && Array.isArray(tree.children) && tree.children.length > 0;
      treeEmptyNode.hidden = hasItems;
      if (!tree) {
        return;
      }
      treeRootNode.appendChild(renderDirectoryNode(tree, true));
    }

    async function refreshTree() {
      const { response, payload } = await fetchJson("/api/list");
      if (!response.ok) {
        throw new Error(payload.message || `读取目录失败（${response.status}）`);
      }
      renderTree(payload.tree);
    }

    async function uploadChunk(task, start, end) {
      const body = task.file.slice(start, end);
      return fetchJson(`/api/upload?path=${encodeURIComponent(task.path)}`, {
        method: "POST",
        headers: {
          "X-Start-Offset": String(start),
          "X-File-Size": String(task.file.size),
          "X-File-Mtime": String(task.file.lastModified),
        },
        body,
      });
    }

    async function probeTask(task) {
      return fetchJson("/api/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: task.path,
          size: task.file.size,
          mtime_ms: task.file.lastModified,
        }),
      });
    }

    async function ensureRemoteDirectories(paths) {
      const unique = Array.from(new Set(paths.filter(Boolean)));
      if (!unique.length) {
        return;
      }
      unique.sort((a, b) => a.split("/").length - b.split("/").length || a.localeCompare(b, "zh-CN"));
      const { response, payload } = await fetchJson("/api/directories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths: unique }),
      });
      if (!response.ok) {
        const details = Array.isArray(payload.conflicts)
          ? payload.conflicts.map((item) => `${item.path}：${item.message}`).join("；")
          : "";
        throw new Error(details || payload.message || `创建目录失败（${response.status}）`);
      }
    }

    async function runUploadTasks(tasks, taskLabel) {
      if (!tasks.length) {
        setStatus(`${taskLabel}没有需要上传的文件。`);
        await refreshTree();
        return;
      }

      setBusyState(true);
      const totalFiles = tasks.length;
      const totalBytes = tasks.reduce((sum, item) => sum + item.file.size, 0);
      let completedFiles = 0;
      let skippedFiles = 0;
      let completedBytes = 0;

      setTaskProgress(0, totalBytes, 0, 0, totalFiles);

      try {
        for (const task of tasks) {
          setStatus(`正在检查：${task.path}`);
          const { response: probeResponse, payload: probePayload } = await probeTask(task);
          if (!probeResponse.ok) {
            throw new Error(probePayload.message || `探测失败（${probeResponse.status}）`);
          }

          if (probePayload.status === "冲突") {
            throw new Error(`${task.path}：${probePayload.message || "目标路径冲突"}`);
          }

          if (probePayload.status === "跳过") {
            completedFiles += 1;
            skippedFiles += 1;
            completedBytes += task.file.size;
            setCurrentProgress(task.file.size, task.file.size, `${task.path} 已存在，已跳过`);
            setTaskProgress(completedBytes, totalBytes, completedFiles, skippedFiles, totalFiles);
            continue;
          }

          let offset = Number(probePayload.offset || 0);
          setCurrentProgress(offset, task.file.size, `准备上传：${task.path}`);
          setTaskProgress(completedBytes + offset, totalBytes, completedFiles, skippedFiles, totalFiles);

          if (task.file.size === 0) {
            const { response, payload } = await uploadChunk(task, 0, 0);
            if (!response.ok) {
              throw new Error(payload.message || `上传失败（${response.status}）`);
            }
            completedFiles += 1;
            completedBytes += 0;
            setCurrentProgress(0, 0, `${task.path} 上传完成`);
            setTaskProgress(completedBytes, totalBytes, completedFiles, skippedFiles, totalFiles);
            continue;
          }

          while (offset < task.file.size) {
            const end = Math.min(offset + chunkSize, task.file.size);
            setStatus(`正在上传：${task.path}`);
            const { response, payload } = await uploadChunk(task, offset, end);

            if (response.status === 409) {
              if (payload.status === "冲突") {
                throw new Error(`${task.path}：${payload.message || "上传冲突"}`);
              }
              if (typeof payload.offset !== "number") {
                throw new Error(`${task.path}：服务器返回了无效的续传位置。`);
              }
              offset = payload.offset;
              setStatus(`已同步服务器进度，继续上传：${task.path}`);
              setCurrentProgress(offset, task.file.size, `续传：${task.path}`);
              setTaskProgress(completedBytes + offset, totalBytes, completedFiles, skippedFiles, totalFiles);
              continue;
            }

            if (!response.ok) {
              throw new Error(payload.message || `上传失败（${response.status}）`);
            }

            offset = Number(payload.offset || end);
            setCurrentProgress(offset, task.file.size, `正在上传：${task.path}`);
            setTaskProgress(completedBytes + offset, totalBytes, completedFiles, skippedFiles, totalFiles);
          }

          completedFiles += 1;
          completedBytes += task.file.size;
          setCurrentProgress(task.file.size, task.file.size, `${task.path} 上传完成`);
          setTaskProgress(completedBytes, totalBytes, completedFiles, skippedFiles, totalFiles);
        }

        await refreshTree();
        setStatus(`${taskLabel}完成，共处理 ${completedFiles} 个文件，其中跳过 ${skippedFiles} 个。`);
      } catch (error) {
        setStatus(error.message || String(error), true);
        throw error;
      } finally {
        setBusyState(false);
      }
    }

    function uploadSingleFile() {
      if (busy) {
        return;
      }
      singleFileInput.value = "";
      singleFileInput.click();
    }

    async function handleSingleFileSelection() {
      if (busy) {
        return;
      }
      const files = Array.from(singleFileInput.files || []);
      singleFileInput.value = "";
      if (!files.length) {
        setStatus("已取消选择文件。");
        return;
      }
      const tasks = files.map((file) => ({ path: joinUploadPath(currentUploadPath, file.name), file }));
      try {
        await runUploadTasks(tasks, "文件上传");
      } catch (error) {
        return;
      }
    }

    async function collectDirectoryTasks(directoryHandle, parentPath = "") {
      const currentPath = parentPath ? `${parentPath}/${directoryHandle.name}` : directoryHandle.name;
      const directories = [currentPath];
      const files = [];
      const entries = [];

      for await (const entry of directoryHandle.values()) {
        entries.push(entry);
      }
      entries.sort((a, b) => {
        if (a.kind === b.kind) {
          return a.name.localeCompare(b.name, "zh-CN");
        }
        return a.kind === "directory" ? -1 : 1;
      });

      for (const entry of entries) {
        if (entry.kind === "directory") {
          const nested = await collectDirectoryTasks(entry, currentPath);
          directories.push(...nested.directories);
          files.push(...nested.files);
          continue;
        }
        const file = await entry.getFile();
        files.push({
          path: `${currentPath}/${entry.name}`,
          file,
        });
      }

      return { rootPath: currentPath, directories, files };
    }

    async function uploadFolder() {
      if (busy) {
        return;
      }
      if (typeof window.showDirectoryPicker !== "function") {
        setStatus("当前浏览器不支持选择文件夹上传。请使用 Chromium，并尽量通过 localhost 或安全上下文访问。", true);
        return;
      }

      try {
        const handle = await window.showDirectoryPicker({ mode: "read" });
        setStatus(`正在读取文件夹：${handle.name}`);
        const collected = await collectDirectoryTasks(handle);
        const directories = collected.directories.map((path) => joinUploadPath(currentUploadPath, path));
        const files = collected.files.map((item) => ({
          path: joinUploadPath(currentUploadPath, item.path),
          file: item.file,
        }));
        await ensureRemoteDirectories(directories);
        if (!files.length) {
          await refreshTree();
          setStatus(`文件夹 ${collected.rootPath} 已创建完成，其中没有文件需要上传。`);
          return;
        }
        await runUploadTasks(files, `文件夹 ${collected.rootPath} 上传`);
      } catch (error) {
        if (error && error.name === "AbortError") {
          setStatus("已取消选择文件夹。");
          return;
        }
        setStatus(error.message || String(error), true);
      }
    }

    async function ensureDirectoryHandle(parentHandle, relativePath) {
      let current = parentHandle;
      if (!relativePath) {
        return current;
      }
      for (const part of relativePath.split("/")) {
        current = await current.getDirectoryHandle(part, { create: true });
      }
      return current;
    }

    async function writeResponseToFile(fileHandle, response, onChunk) {
      const writable = await fileHandle.createWritable();
      let written = 0;
      try {
        if (!response.body) {
          const arrayBuffer = await response.arrayBuffer();
          const data = new Uint8Array(arrayBuffer);
          if (data.byteLength) {
            await writable.write(data);
            written += data.byteLength;
            onChunk(data.byteLength, written);
          }
        } else {
          const reader = response.body.getReader();
          while (true) {
            const { value, done } = await reader.read();
            if (done) {
              break;
            }
            if (value && value.byteLength) {
              await writable.write(value);
              written += value.byteLength;
              onChunk(value.byteLength, written);
            }
          }
        }
        await writable.close();
        return written;
      } catch (error) {
        try {
          await writable.abort();
        } catch (_) {
        }
        throw error;
      }
    }

    async function downloadDirectoryNode(node) {
      if (busy) {
        return;
      }
      if (!node || node.type !== "目录") {
        setStatus("当前节点不是目录，无法下载。", true);
        return;
      }
      if (typeof window.showDirectoryPicker !== "function") {
        setStatus("当前浏览器不支持把目录直接写入本地路径。请使用 Chromium，并尽量通过 localhost 或安全上下文访问。", true);
        return;
      }

      const entries = collectTreeEntries(node, node.path);
      const totalFiles = entries.files.length;
      const totalBytes = entries.files.reduce((sum, item) => sum + (item.size || 0), 0);

      setBusyState(true);
      try {
        const targetRootHandle = await window.showDirectoryPicker({ mode: "readwrite" });
        const topDirectoryName = node.name || "下载目录";
        const topDirectoryHandle = await targetRootHandle.getDirectoryHandle(topDirectoryName, { create: true });

        for (const directoryPath of entries.directories) {
          await ensureDirectoryHandle(topDirectoryHandle, directoryPath);
        }

        let completedFiles = 0;
        let completedBytes = 0;
        setTaskProgress(0, totalBytes, 0, 0, totalFiles);

        for (const file of entries.files) {
          const relativePath = file.relativePath;
          const pathParts = relativePath.split("/");
          const fileName = pathParts.pop();
          const parentRelative = pathParts.join("/");
          const parentHandle = await ensureDirectoryHandle(topDirectoryHandle, parentRelative);
          const fileHandle = await parentHandle.getFileHandle(fileName, { create: true });

          setStatus(`正在下载：${file.path}`);
          let currentDone = 0;
          setCurrentProgress(0, file.size, `下载：${file.path}`);

          const response = await fetch(file.download_url);
          if (!response.ok) {
            throw new Error(`${file.path} 下载失败（${response.status}）`);
          }

          await writeResponseToFile(fileHandle, response, (delta, written) => {
            currentDone = written;
            completedBytes += delta;
            setCurrentProgress(currentDone, file.size, `下载：${file.path}`);
            setTaskProgress(completedBytes, totalBytes, completedFiles, 0, totalFiles);
          });

          completedFiles += 1;
          setCurrentProgress(file.size, file.size, `${file.path} 下载完成`);
          setTaskProgress(completedBytes, totalBytes, completedFiles, 0, totalFiles);
        }

        if (!entries.files.length) {
          setCurrentProgress(0, 0, `${node.path || node.name} 是空目录`);
          setTaskProgress(0, 0, 0, 0, 0);
        }
        setStatus(`目录 ${node.path || node.name} 已写入你选择的本地路径。`);
      } catch (error) {
        if (error && error.name === "AbortError") {
          setStatus("已取消目录下载。");
        } else {
          setStatus(error.message || String(error), true);
        }
      } finally {
        setBusyState(false);
      }
    }

    uploadFileButton.addEventListener("click", uploadSingleFile);
    singleFileInput.addEventListener("change", handleSingleFileSelection);
    uploadFolderButton.addEventListener("click", uploadFolder);
    resetUploadTargetButton.addEventListener("click", () => {
      if (busy || !currentUploadPath) {
        return;
      }
      setUploadTarget("");
    });

    resetProgress();
    setBusyState(false);
    updateUploadTargetView();
    refreshTree().catch((error) => {
      setStatus(error.message || String(error), true);
    });
  </script>
</body>
</html>
"""


LOGIN_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>登录 咩FileServer</title>
  <style>
    :root {
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
      --bg: #eef7ff;
      --card: rgba(255, 255, 255, 0.94);
      --line: #c8dceb;
      --ink: #12324a;
      --muted: #5d7790;
      --danger: #b42318;
      --accent: #1f89e5;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at top, rgba(111, 187, 255, 0.22), transparent 28%),
        linear-gradient(180deg, #eef7ff 0%, #f7fbff 100%);
      color: var(--ink);
      padding: 16px;
    }
    .card {
      width: min(440px, 100%);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 28px;
      box-shadow: 0 18px 46px rgba(18, 50, 74, 0.08);
    }
    h1 {
      margin: 0 0 8px;
      font-size: 2rem;
    }
    p {
      margin: 0 0 18px;
      line-height: 1.7;
      color: var(--muted);
    }
    form {
      display: grid;
      gap: 12px;
    }
    input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 1rem;
    }
    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    .error {
      min-height: 1.5em;
      margin-top: 12px;
      color: var(--danger);
      font-weight: 600;
    }
  </style>
</head>
<body>
  <section class="card">
    <h1>咩FileServer</h1>
    <p>当前共享目录已启用访问密码。请输入密码后继续</p>
    <form method="post" action="/login">
      <input type="password" name="password" autocomplete="current-password" autofocus required placeholder="请输入密码">
      <button type="submit">登录</button>
    </form>
    <div class="error">__MESSAGE__</div>
  </section>
</body>
</html>
"""


@dataclass
class AppState:
    root: Path
    password: str
    sessions: dict[str, float] = field(default_factory=dict)
    session_lock: threading.Lock = field(default_factory=threading.Lock)
    file_locks: dict[str, threading.Lock] = field(default_factory=dict)
    file_locks_lock: threading.Lock = field(default_factory=threading.Lock)

    def auth_enabled(self) -> bool:
        return bool(self.password)

    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + SESSION_TTL_SECONDS
        with self.session_lock:
            self.sessions[token] = expires_at
        return token

    def validate_session(self, token: str) -> bool:
        now = time.time()
        with self.session_lock:
            expires_at = self.sessions.get(token)
            if expires_at is None:
                return False
            if expires_at < now:
                self.sessions.pop(token, None)
                return False
            self.sessions[token] = now + SESSION_TTL_SECONDS
            return True

    def get_file_lock(self, relative_path: str) -> threading.Lock:
        with self.file_locks_lock:
            lock = self.file_locks.get(relative_path)
            if lock is None:
                lock = threading.Lock()
                self.file_locks[relative_path] = lock
            return lock


class MeFileHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], state: AppState):
        super().__init__(server_address, handler_class)
        self.state = state


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def display_root_name(root: Path) -> str:
    if root.name:
        return root.name
    if root.drive:
        return root.drive
    return "根目录"


def normalize_relative_path(raw_path: str, *, allow_empty: bool = False) -> str:
    if raw_path is None:
        raise ValueError("路径不能为空")
    value = str(raw_path).strip().replace("\\", "/")
    drive, _ = os.path.splitdrive(value)
    if drive:
        raise ValueError("不允许使用绝对路径")
    if value.startswith("/"):
        raise ValueError("不允许使用绝对路径")
    if not value:
        if allow_empty:
            return ""
        raise ValueError("路径不能为空")

    parts: list[str] = []
    for part in value.split("/"):
        if part in {"", ".", ".."}:
            raise ValueError("路径中包含非法片段")
        if "\x00" in part:
            raise ValueError("路径中包含非法字符")
        if part.endswith(SIDECAR_SUFFIX) or part.endswith(SIDECAR_SUFFIX + ".tmp"):
            raise ValueError("不允许直接操作进度文件")
        parts.append(part)

    normalized = "/".join(parts)
    if not normalized and not allow_empty:
        raise ValueError("路径不能为空")
    return normalized


def split_relative_path(relative_path: str) -> list[str]:
    if not relative_path:
        return []
    return relative_path.split("/")


def resolve_relative_path(root: Path, relative_path: str) -> Path:
    current = root
    for part in split_relative_path(relative_path):
        current = current / part
    return current


def sidecar_path(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + SIDECAR_SUFFIX)


def sidecar_temp_path(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + SIDECAR_SUFFIX + ".tmp")


def atomic_write_sidecar(file_path: Path, *, size: int, mtime_ms: int, received: int) -> None:
    payload = {
        "version": 1,
        "name": file_path.name,
        "size": size,
        "mtime_ms": mtime_ms,
        "received": received,
        "updated_at": utc_now_iso(),
    }
    temp_path = sidecar_temp_path(file_path)
    final_path = sidecar_path(file_path)
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp_path, final_path)


def remove_sidecar(file_path: Path) -> None:
    try:
        sidecar_path(file_path).unlink()
    except FileNotFoundError:
        pass


def load_sidecar(file_path: Path) -> dict[str, Any] | None:
    target = sidecar_path(file_path)
    if not target.exists():
        return None
    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return {
            "version": int(payload.get("version", 1)),
            "name": str(payload["name"]),
            "size": int(payload["size"]),
            "mtime_ms": int(payload["mtime_ms"]),
            "received": int(payload["received"]),
            "updated_at": str(payload.get("updated_at", "")),
        }
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"invalid": True}


def check_directory_chain(root: Path, relative_path: str, *, include_last: bool) -> str | None:
    parts = split_relative_path(relative_path)
    limit = len(parts) if include_last else max(len(parts) - 1, 0)
    current = root
    walked: list[str] = []
    for part in parts[:limit]:
        current = current / part
        walked.append(part)
        if current.exists() and not current.is_dir():
            return f"路径已被文件占用：{'/'.join(walked)}"
    return None


def ensure_directory_path(dir_path: Path) -> tuple[bool, str | None, bool]:
    existed = dir_path.exists() and dir_path.is_dir()
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        return False, "目标路径已被文件占用", False
    except NotADirectoryError:
        return False, "上级路径不是目录", False
    except OSError as exc:
        return False, f"无法创建目录：{exc}", False
    return True, None, not existed


def inspect_upload_state(file_path: Path, incoming_size: int | None = None, incoming_mtime_ms: int | None = None) -> dict[str, Any]:
    if file_path.exists() and file_path.is_dir():
        return {"status": "冲突", "offset": 0, "message": "目标路径已存在同名目录"}

    actual_size = file_path.stat().st_size if file_path.is_file() else 0
    progress = load_sidecar(file_path)

    if progress:
        if progress.get("invalid"):
            return {"status": "冲突", "offset": actual_size, "message": "进度文件损坏，无法继续续传"}

        expected_size = progress["size"]
        expected_mtime = progress["mtime_ms"]
        offset = min(progress["received"], actual_size)

        if incoming_size is not None and incoming_mtime_ms is not None:
            if incoming_size != expected_size or incoming_mtime_ms != expected_mtime:
                return {"status": "冲突", "offset": offset, "message": "同名文件的来源信息不匹配，无法续传"}

        if offset >= expected_size:
            if file_path.exists() and file_path.is_file() and actual_size != expected_size:
                with file_path.open("r+b") as handle:
                    handle.truncate(expected_size)
            elif not file_path.exists() and expected_size == 0:
                file_path.touch()
            remove_sidecar(file_path)
            return {"status": "跳过", "offset": expected_size, "message": "服务器上已存在完整文件，已跳过"}

        return {
            "status": "续传",
            "offset": offset,
            "size": expected_size,
            "mtime_ms": expected_mtime,
            "message": "找到未完成上传，将从已有进度继续",
        }

    if file_path.exists():
        if file_path.is_file():
            return {"status": "跳过", "offset": actual_size, "message": "服务器上已存在完整文件，已跳过"}
        return {"status": "冲突", "offset": 0, "message": "目标路径已存在同名目录"}

    return {"status": "新文件", "offset": 0, "message": "这是一个新文件，将从头开始上传"}


def build_tree_node(root: Path, current_path: str = "") -> dict[str, Any] | None:
    absolute_path = root if not current_path else resolve_relative_path(root, current_path)
    name = display_root_name(root) if not current_path else absolute_path.name

    try:
        stat = absolute_path.stat()
    except OSError:
        if current_path:
            return None
        return {
            "type": "目录",
            "name": name,
            "path": current_path,
            "mtime": 0,
            "children": [],
        }

    children: list[dict[str, Any]] = []
    try:
        entries = [
            entry
            for entry in absolute_path.iterdir()
            if not entry.name.endswith(SIDECAR_SUFFIX) and not entry.name.endswith(SIDECAR_SUFFIX + ".tmp")
        ]
    except OSError:
        if current_path:
            return None
        entries = []

    def entry_sort_key(item: Path) -> tuple[int, str]:
        try:
            is_dir = item.is_dir()
        except OSError:
            is_dir = False
        return (0 if is_dir else 1, item.name.lower())

    entries.sort(key=entry_sort_key)

    for entry in entries:
        entry_path = f"{current_path}/{entry.name}" if current_path else entry.name
        try:
            if entry.is_dir():
                child = build_tree_node(root, entry_path)
                if child is not None:
                    children.append(child)
                continue
            if entry.is_file():
                entry_stat = entry.stat()
                children.append(
                    {
                        "type": "文件",
                        "name": entry.name,
                        "path": entry_path,
                        "size": entry_stat.st_size,
                        "mtime": int(entry_stat.st_mtime * 1000),
                        "download_url": "/download?path=" + quote(entry_path, safe=""),
                    }
                )
        except OSError:
            continue

    return {
        "type": "目录",
        "name": name,
        "path": current_path,
        "mtime": int(stat.st_mtime * 1000),
        "children": children,
    }


def parse_single_range(header_value: str, file_size: int) -> tuple[int, int] | None:
    if file_size <= 0 or not header_value.startswith("bytes="):
        return None
    raw_range = header_value[6:].strip()
    if "," in raw_range:
        return None
    start_text, sep, end_text = raw_range.partition("-")
    if not sep:
        return None
    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            if suffix_length >= file_size:
                return 0, file_size - 1
            return file_size - suffix_length, file_size - 1

        start = int(start_text)
        if start < 0 or start >= file_size:
            return None

        if end_text == "":
            return start, file_size - 1

        end = int(end_text)
        if end < start:
            return None
        return start, min(end, file_size - 1)
    except ValueError:
        return None


class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def state(self) -> AppState:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                if self.state.auth_enabled() and not self.is_authenticated():
                    self.send_html(HTTPStatus.OK, render_login_page(""))
                    return
                self.send_html(HTTPStatus.OK, render_home_page(self.state.root))
                return

            if parsed.path == "/api/list":
                if not self.ensure_authenticated(api=True):
                    return
                self.send_json(HTTPStatus.OK, {"status": "成功", "tree": build_tree_node(self.state.root)})
                return

            if parsed.path == "/download":
                if not self.ensure_authenticated(api=False):
                    return
                self.handle_download(parsed.query)
                return

            if parsed.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_error_text(HTTPStatus.NOT_FOUND, "未找到对应页面。")
        except Exception:
            self.handle_unexpected_error()

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/login":
                self.handle_login()
                return

            if parsed.path == "/api/probe":
                if not self.ensure_authenticated(api=True):
                    return
                self.handle_probe()
                return

            if parsed.path == "/api/directories":
                if not self.ensure_authenticated(api=True):
                    return
                self.handle_directories()
                return

            if parsed.path == "/api/upload":
                if not self.ensure_authenticated(api=True):
                    return
                self.handle_upload(parsed.query)
                return

            self.send_error_text(HTTPStatus.NOT_FOUND, "未找到对应接口。")
        except Exception:
            self.handle_unexpected_error()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), fmt % args)
        )

    def handle_unexpected_error(self) -> None:
        traceback.print_exc()
        try:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "服务器内部发生错误"})
        except BrokenPipeError:
            pass

    def is_authenticated(self) -> bool:
        if not self.state.auth_enabled():
            return True
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return False
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except Exception:
            return False
        morsel = cookie.get(SESSION_COOKIE_NAME)
        if morsel is None:
            return False
        return self.state.validate_session(morsel.value)

    def ensure_authenticated(self, *, api: bool) -> bool:
        if self.is_authenticated():
            return True
        if api:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"message": "需要先登录才能访问此接口"})
        else:
            self.send_error_text(HTTPStatus.UNAUTHORIZED, "需要先登录才能访问该资源。")
        return False

    def read_request_body(self, max_bytes: int | None = None) -> bytes:
        length = self.get_content_length()
        if max_bytes is not None and length > max_bytes:
            raise ValueError("请求体过大")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("请求体读取不完整")
        return body

    def get_content_length(self) -> int:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("缺少 Content-Length")
        length = int(raw_length)
        if length < 0:
            raise ValueError("Content-Length 非法")
        return length

    def send_json(self, status: HTTPStatus, payload: dict[str, Any], extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_bytes(status, body, "application/json; charset=utf-8", extra_headers)

    def send_html(self, status: HTTPStatus, page: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_bytes(status, page.encode("utf-8"), "text/html; charset=utf-8", extra_headers)

    def send_error_text(self, status: HTTPStatus, message: str) -> None:
        self.send_bytes(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def send_redirect(self, location: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def reject_upload(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        # 上传请求若被提前拒绝，仍可能有未读完的 body 残留在连接里，
        # 这里直接关闭 keep-alive，避免剩余字节被当成下一条 HTTP 请求。
        self.close_connection = True
        self.send_json(status, payload, {"Connection": "close"})

    def parse_query_path(self, query: str, *, allow_empty: bool = False) -> str:
        params = parse_qs(query, keep_blank_values=True)
        raw_path = params.get("path", [""])[0]
        return normalize_relative_path(raw_path, allow_empty=allow_empty)

    def handle_login(self) -> None:
        if not self.state.auth_enabled():
            self.send_redirect("/")
            return

        try:
            body = self.read_request_body(max_bytes=16 * 1024)
        except ValueError as exc:
            self.send_html(HTTPStatus.BAD_REQUEST, render_login_page(str(exc)))
            return

        params = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        password = params.get("password", [""])[0]
        if not secrets.compare_digest(password, self.state.password):
            self.send_html(HTTPStatus.UNAUTHORIZED, render_login_page("密码不正确。"))
            return

        token = self.state.create_session()
        cookie = f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL_SECONDS}"
        self.send_redirect("/", {"Set-Cookie": cookie})

    def handle_directories(self) -> None:
        try:
            body = self.read_request_body(max_bytes=256 * 1024)
            payload = json.loads(body.decode("utf-8"))
            raw_paths = payload["paths"]
            if not isinstance(raw_paths, list):
                raise ValueError("paths 必须是数组")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"message": "目录请求体格式不正确"})
            return

        created: list[str] = []
        skipped: list[str] = []
        conflicts: list[dict[str, str]] = []
        seen: set[str] = set()

        normalized_paths: list[str] = []
        try:
            for item in raw_paths:
                path = normalize_relative_path(str(item), allow_empty=True)
                if not path or path in seen:
                    continue
                seen.add(path)
                normalized_paths.append(path)
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"message": str(exc)})
            return

        normalized_paths.sort(key=lambda item: (len(split_relative_path(item)), item))

        for relative_path in normalized_paths:
            chain_conflict = check_directory_chain(self.state.root, relative_path, include_last=True)
            if chain_conflict:
                conflicts.append({"path": relative_path, "message": chain_conflict})
                continue

            absolute_path = resolve_relative_path(self.state.root, relative_path)
            ok, message, was_created = ensure_directory_path(absolute_path)
            if not ok:
                conflicts.append({"path": relative_path, "message": message or "创建目录失败"})
            elif was_created:
                created.append(relative_path)
            else:
                skipped.append(relative_path)

        response = {
            "status": "成功" if not conflicts else "冲突",
            "created": created,
            "skipped": skipped,
            "conflicts": conflicts,
            "message": "目录已处理完成" if not conflicts else "部分目录无法创建",
        }
        if conflicts:
            self.send_json(HTTPStatus.CONFLICT, response)
            return
        self.send_json(HTTPStatus.OK, response)

    def handle_probe(self) -> None:
        try:
            body = self.read_request_body(max_bytes=64 * 1024)
            payload = json.loads(body.decode("utf-8"))
            relative_path = normalize_relative_path(str(payload["path"]))
            size = int(payload["size"])
            mtime_ms = int(payload["mtime_ms"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"message": "探测请求体格式不正确"})
            return

        if size < 0 or mtime_ms < 0:
            self.send_json(HTTPStatus.BAD_REQUEST, {"message": "文件元信息不合法"})
            return

        chain_conflict = check_directory_chain(self.state.root, relative_path, include_last=False)
        if chain_conflict:
            self.send_json(HTTPStatus.OK, {"status": "冲突", "offset": 0, "message": chain_conflict})
            return

        file_path = resolve_relative_path(self.state.root, relative_path)
        file_lock = self.state.get_file_lock(relative_path)
        with file_lock:
            result = inspect_upload_state(file_path, size, mtime_ms)
        self.send_json(HTTPStatus.OK, result)

    def handle_upload(self, query: str) -> None:
        try:
            relative_path = self.parse_query_path(query)
            start_offset = int(self.headers.get("X-Start-Offset", ""))
            file_size = int(self.headers.get("X-File-Size", ""))
            file_mtime = int(self.headers.get("X-File-Mtime", ""))
            content_length = self.get_content_length()
        except (ValueError, TypeError):
            self.reject_upload(HTTPStatus.BAD_REQUEST, {"message": "上传请求头不合法"})
            return

        if start_offset < 0 or file_size < 0 or file_mtime < 0:
            self.reject_upload(HTTPStatus.BAD_REQUEST, {"message": "上传请求头不合法"})
            return
        if start_offset > file_size:
            self.reject_upload(HTTPStatus.BAD_REQUEST, {"message": "上传起始偏移超过了文件总长度"})
            return
        if content_length > file_size - start_offset:
            self.reject_upload(HTTPStatus.BAD_REQUEST, {"message": "本次上传片段超出了目标文件长度"})
            return

        chain_conflict = check_directory_chain(self.state.root, relative_path, include_last=False)
        if chain_conflict:
            self.reject_upload(HTTPStatus.CONFLICT, {"status": "冲突", "offset": 0, "message": chain_conflict})
            return

        file_path = resolve_relative_path(self.state.root, relative_path)
        file_lock = self.state.get_file_lock(relative_path)

        with file_lock:
            ok, message, _ = ensure_directory_path(file_path.parent)
            if not ok:
                self.reject_upload(HTTPStatus.CONFLICT, {"status": "冲突", "offset": 0, "message": message or "无法创建上级目录"})
                return

            state = inspect_upload_state(file_path, file_size, file_mtime)
            current_offset = int(state.get("offset", 0))
            if state["status"] == "冲突":
                self.reject_upload(HTTPStatus.CONFLICT, state)
                return

            if start_offset != current_offset:
                state["message"] = state.get("message", "上传偏移与服务器记录不一致")
                self.reject_upload(HTTPStatus.CONFLICT, state)
                return

            if state["status"] == "跳过" and current_offset >= file_size:
                self.send_json(HTTPStatus.OK, {"status": "成功", "offset": current_offset, "complete": True, "message": "文件已存在，跳过上传"})
                return

            bytes_written = 0
            bytes_since_flush = 0
            atomic_write_sidecar(file_path, size=file_size, mtime_ms=file_mtime, received=current_offset)

            mode = "r+b" if file_path.exists() and file_path.is_file() else "w+b"
            try:
                with file_path.open(mode) as handle:
                    handle.seek(start_offset)
                    remaining = content_length
                    while remaining > 0:
                        chunk = self.rfile.read(min(UPLOAD_READ_CHUNK, remaining))
                        if not chunk:
                            raise ConnectionError("客户端在上传过程中断开了连接")
                        handle.write(chunk)
                        remaining -= len(chunk)
                        bytes_written += len(chunk)
                        bytes_since_flush += len(chunk)
                        if bytes_since_flush >= PROGRESS_FLUSH_BYTES:
                            atomic_write_sidecar(
                                file_path,
                                size=file_size,
                                mtime_ms=file_mtime,
                                received=start_offset + bytes_written,
                            )
                            bytes_since_flush = 0

                    final_offset = start_offset + bytes_written
                    atomic_write_sidecar(file_path, size=file_size, mtime_ms=file_mtime, received=final_offset)
                    complete = final_offset >= file_size
                    if complete:
                        handle.truncate(file_size)
                        remove_sidecar(file_path)
                    response = {
                        "status": "成功",
                        "offset": final_offset,
                        "complete": complete,
                        "message": "上传完成" if complete else "片段写入成功",
                    }
            except ConnectionError:
                final_offset = start_offset + bytes_written
                atomic_write_sidecar(file_path, size=file_size, mtime_ms=file_mtime, received=final_offset)
                raise

        self.send_json(HTTPStatus.OK, response)

    def handle_download(self, query: str) -> None:
        try:
            relative_path = self.parse_query_path(query)
        except ValueError:
            self.send_error_text(HTTPStatus.BAD_REQUEST, "下载路径不合法。")
            return

        file_path = resolve_relative_path(self.state.root, relative_path)
        if not file_path.is_file():
            self.send_error_text(HTTPStatus.NOT_FOUND, "未找到要下载的文件。")
            return

        file_size = file_path.stat().st_size
        start = 0
        end = file_size - 1
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")

        if range_header:
            byte_range = parse_single_range(range_header, file_size)
            if byte_range is None:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            start, end = byte_range
            status = HTTPStatus.PARTIAL_CONTENT

        content_length = max(0, end - start + 1)
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        content_disposition = f"attachment; filename*=UTF-8''{quote(file_path.name, safe='')}"

        self.send_response(status)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", content_disposition)
        self.send_header("Cache-Control", "no-store")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()

        with file_path.open("rb") as handle:
            if content_length == 0:
                return
            handle.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk = handle.read(min(DOWNLOAD_CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def render_home_page(root: Path) -> str:
    return HOME_PAGE.replace("__ROOT__", html.escape(str(root)))


def render_login_page(message: str) -> str:
    return LOGIN_PAGE.replace("__MESSAGE__", html.escape(message))


def prompt_password() -> str:
    try:
        return getpass.getpass("共享访问密码（直接回车就不用密码，输入的密码不会显示）：")
    except EOFError:
        print("\n当前环境无法交互输入密码，将以无鉴权模式启动。", file=sys.stderr)
        return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="咩FileServer：单文件脚本的目录化断点续传文件服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址，默认：%(default)s")
    parser.add_argument("--port", type=int, default=8000, help="监听端口，默认：%(default)s")
    parser.add_argument("--root", default=".", help="共享根目录，默认：当前目录")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        parser.error(f"共享根目录不存在，或者它不是一个目录：{root}")

    password = prompt_password()
    state = AppState(root=root, password=password)
    server = MeFileHTTPServer((args.host, args.port), RequestHandler, state)

    auth_note = "已启用密码" if password else "未启用密码"
    print(f"咩FileServer 已启动：{root}")
    print(f"访问地址：http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭 咩FileServer。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
