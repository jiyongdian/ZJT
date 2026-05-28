// ============================
// extract_frame_node.js - 提取帧节点
// 使用 createNodeBase 基类工厂
// ============================

(function() {

  var EXTRACT_FRAME_PORTS = [
    { direction: 'input', titleI18nKey: 'extract_frame_input_port', acceptType: 'video', connectionType: 'connections' },
    { direction: 'output', titleI18nKey: 'extract_frame_output_port' }
  ];

  function createExtractFrameNode(opts) {
    return createNodeBase({
      type: 'extract_frame',
      title: function() { return window.t ? window.t('extract_frame_title') : '提取帧'; },
      defaultData: {
        videoFile: null,
        videoUrl: '',
        videoName: '',
        frameType: 'first',
        extractedImageNodeId: null,
        status: 'idle'
      },
      ports: EXTRACT_FRAME_PORTS,
      width: 280,
      height: 250,
      titleIcon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><rect x="4" y="6" width="16" height="12" rx="2"/><path d="M10 9.5V14.5L14.5 12L10 9.5Z" fill="currentColor" /><rect x="6" y="2" width="6" height="4" rx="1" stroke="currentColor" stroke-width="2" /></svg>',
      bodyHtml: function() {
        return '<div class="field field-collapsible">' +
          '<div class="label" data-i18n="video">视频</div>' +
          '<input class="video-file" type="file" accept="video/*" />' +
        '</div>' +
        '<div class="field field-always-visible video-preview-field" style="display:none;">' +
          '<div class="label" data-i18n="video_preview">预览</div>' +
          '<div class="video-preview"><video class="video-thumb" playsinline muted></video></div>' +
          '<div class="gen-meta video-name"></div>' +
        '</div>' +
        '<div class="field field-always-visible frame-type-field">' +
          '<div class="label" data-i18n="frame_type">帧类型</div>' +
          '<select class="frame-type-select">' +
            '<option value="first" data-i18n="frame_first">首帧</option>' +
            '<option value="last" data-i18n="frame_last">尾帧</option>' +
          '</select>' +
        '</div>' +
        '<div class="field field-always-visible extract-actions-field">' +
          '<button class="gen-btn" type="button" data-i18n="extract_frame_btn" title="提取帧">提取帧</button>' +
        '</div>' +
        '<div class="field field-always-visible status-field" style="display:none;">' +
          '<div class="gen-meta status"></div>' +
        '</div>';
      },
      onCreated: function(node, el) {
        var fileEl = el.querySelector('.video-file');
        var previewField = el.querySelector('.video-preview-field');
        var thumbVideo = el.querySelector('.video-thumb');
        var nameEl = el.querySelector('.video-name');
        var frameTypeSelect = el.querySelector('.frame-type-select');
        var extractBtn = el.querySelector('.gen-btn');
        var statusField = el.querySelector('.status-field');
        var statusEl = el.querySelector('.status');

        // 绑定输入端口连接事件
        bindInputPortEvents(el, node, {
          cssClass: null,
          acceptType: 'video',
          connectionType: 'connections',
          onConnect: function(fromNode) {
            node.data.videoUrl = fromNode.data.url;
            node.data.videoName = fromNode.data.name || '视频';
            if (node.data.videoUrl) {
              thumbVideo.src = proxyDownloadUrl(node.data.videoUrl);
              previewField.style.display = '';
              nameEl.textContent = node.data.videoName;
            }
          }
        });

        // 设置视频
        function setVideoFromUrl(url, name) {
          node.data.videoUrl = url || '';
          node.data.videoName = name || '';
          thumbVideo.src = url ? proxyDownloadUrl(url) : '';
          previewField.style.display = url ? '' : 'none';
          nameEl.textContent = name || '';
        }

        function clearResult() {
          node.data.extractedImageNodeId = null;
          node.data.status = 'idle';
          statusField.style.display = 'none';
          setBtnReady(extractBtn, window.t ? window.t('extract_frame_btn') : '提取帧');
        }

        // 视频文件上传
        fileEl.addEventListener('change', async function(e) {
          var file = e.target.files[0];
          if (!file) return;
          if (!file.type.startsWith('video/')) {
            showToast(window.t ? window.t('extract_frame_select_video') : '请选择视频文件', 'error');
            return;
          }
          try {
            showToast('正在处理视频...', 'info');
            var dataUrl = await readFileAsDataUrl(file);
            node.data.videoFile = file;
            node.data.videoName = file.name;
            node.data.videoUrl = dataUrl;
            thumbVideo.src = dataUrl;
            previewField.style.display = '';
            nameEl.textContent = file.name;
            clearResult();
            showToast(window.t ? window.t('extract_frame_loaded') : '视频已加载，点击"提取帧"按钮提取', 'success');
            safeAutoSave();
          } catch (error) {
            console.error('视频处理失败:', error);
            showToast(window.t ? window.t('extract_frame_failed') : '视频处理失败', 'error');
          }
        });

        // 帧类型选择
        frameTypeSelect.addEventListener('change', function(e) {
          node.data.frameType = e.target.value;
          safeAutoSave();
        });

        // 提取帧按钮
        extractBtn.addEventListener('click', async function(e) {
          e.stopPropagation();
          await extractFrame();
        });

        async function extractFrame() {
          var hasVideoFile = node.data.videoFile !== null;
          var hasVideoUrl = node.data.videoUrl && node.data.videoUrl.length > 0;

          if (!hasVideoFile && !hasVideoUrl) {
            showToast(window.t ? window.t('extract_frame_no_video') : '请先上传视频或连接视频节点', 'error');
            return;
          }

          var frameType = node.data.frameType || 'first';
          var frameTypeName = frameType === 'last' ? '尾帧' : '首帧';

          node.data.status = 'extracting';
          statusField.style.display = '';
          statusEl.textContent = '正在提取' + frameTypeName + '...';
          setBtnLoading(extractBtn, window.t ? window.t('extract_frame_extracting') : '提取中...');

          try {
            var formData = new FormData();
            var isServerUrl = node.data.videoUrl && (node.data.videoUrl.startsWith('/upload/') || node.data.videoUrl.includes('/upload/'));

            if (hasVideoFile && !isServerUrl) {
              formData.append('file', node.data.videoFile);
            } else if (node.data.videoUrl) {
              formData.append('video_url', node.data.videoUrl);
            } else {
              showToast('没有可提取的视频', 'error');
              extractBtn.disabled = false;
              extractBtn.textContent = window.t ? window.t('extract_frame_btn') : '提取帧';
              return;
            }

            formData.append('frame_type', frameType);

            var response = await fetch('/api/video-workflow/extract-frame', {
              method: 'POST',
              headers: {
                'Authorization': localStorage.getItem('auth_token') || '',
                'X-User-Id': localStorage.getItem('user_id') || '1'
              },
              body: formData
            });

            var result = await response.json();

            if (result.code === 0 && result.data && result.data.url) {
              var imageUrl = result.data.url;
              node.data.status = 'success';
              statusEl.textContent = '提取成功，正在创建图片节点...';
              statusEl.style.color = '#22c55e';

              var imageNodeId = createImageNode({ x: node.x + 280, y: node.y, checkCollision: true });
              var imageNode = state.nodes.find(function(n) { return n.id === imageNodeId; });
              if (imageNode) {
                imageNode.data.url = imageUrl;
                imageNode.data.preview = imageUrl;
                imageNode.data.name = node.data.videoName ? node.data.videoName.replace(/\.[^.]+$/, '_' + frameTypeName + '.png') : frameTypeName + '.png';

                var imageNodeEl = canvasEl.querySelector('.node[data-node-id="' + imageNodeId + '"]');
                if (imageNodeEl) {
                  var previewRow = imageNodeEl.querySelector('.image-preview-row');
                  var previewImg = imageNodeEl.querySelector('.image-preview');
                  if (previewRow && previewImg) {
                    previewRow.style.display = 'flex';
                    previewImg.src = imageUrl;
                  }
                }

                state.imageConnections.push({
                  id: state.nextImgConnId++,
                  from: node.id,
                  to: imageNodeId,
                  portType: 'extracted'
                });

                node.data.extractedImageNodeId = imageNodeId;

                requestAnimationFrame(function() {
                  renderAllConnections();
                });
              }

              setTimeout(function() { statusField.style.display = 'none'; }, 2000);
              showToast(frameTypeName + '提取成功，已创建图片节点', 'success');
              renderMinimap();
              safeAutoSave();
            } else {
              node.data.status = 'error';
              statusEl.textContent = result.message || '提取失败';
              statusEl.style.color = '#ef4444';
              showToast(result.message || '提取' + frameTypeName + '失败', 'error');
            }
          } catch (error) {
            console.error('提取帧失败:', error);
            node.data.status = 'error';
            statusEl.textContent = '网络错误';
            statusEl.style.color = '#ef4444';
            showToast('提取' + frameTypeName + '失败，请检查网络连接', 'error');
          } finally {
            extractBtn.disabled = false;
            extractBtn.textContent = window.t ? window.t('extract_frame_btn') : '提取帧';
          }
        }
      }
    }, opts);
  }

  var createExtractFrameNodeWithData = createNodeWithDataFactory(
    createExtractFrameNode,
    function(el, node) {
      var previewField = el.querySelector('.video-preview-field');
      var thumbVideo = el.querySelector('.video-thumb');
      var nameEl = el.querySelector('.video-name');

      if (node.data.videoUrl) {
        thumbVideo.src = proxyDownloadUrl(node.data.videoUrl);
        previewField.style.display = '';
        nameEl.textContent = node.data.videoName;
      }

      if (node.data.frameType) {
        var frameTypeSelect = el.querySelector('.frame-type-select');
        if (frameTypeSelect) frameTypeSelect.value = node.data.frameType;
      }
    }
  );

  // 注册到全局
  window.createExtractFrameNode = createExtractFrameNode;
  window.createExtractFrameNodeWithData = createExtractFrameNodeWithData;

  // 注册到节点注册表
  registerNodeType('extract_frame', {
    createFn: createExtractFrameNode,
    createWithDataFn: createExtractFrameNodeWithData
  });

})();
