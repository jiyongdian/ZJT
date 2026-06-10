// ============================
// digital_human_node.js - 数字人节点
// 使用 createNodeBase 基类工厂
// 输入：图片（可连接图片节点）、音频（可连接音频节点）、提示词
// 输出：视频
// ============================

(function() {

  // 默认提示词
  var DEFAULT_PROMPT = '角色面向镜头深情的说话，固定镜头。';

  // 安全翻译函数：当 window.t 返回原始键名时（翻译未加载），使用 fallback
  function _t(key, fallback) {
    if (typeof window.t !== 'function') return fallback;
    var result = window.t(key);
    return result === key ? fallback : result;
  }

  function createDigitalHumanNode(opts) {
    return createNodeBase({
      type: 'digital_human',
      title: function() { return _t('dh_title', '数字人'); },
      defaultData: {
        prompt: opts?.data?.prompt || DEFAULT_PROMPT,
        imageFile: null,
        imageUrl: opts?.data?.imageUrl || '',
        imagePreview: opts?.data?.imagePreview || '',
        audioFile: null,
        audioUrl: opts?.data?.audioUrl || '',
        videoUrl: opts?.data?.videoUrl || '',
        projectId: null,
        status: opts?.data?.status || ''
      },
      ports: [
        { direction: 'output', titleI18nKey: 'dh_output_port' }
      ],
      width: 300,
      height: 340,
      titleIcon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><circle cx="12" cy="8" r="4"/><path d="M6 21C6 17.6863 8.68629 15 12 15C15.3137 15 18 17.6863 18 21"/></svg>',
      bodyHtml: function() {
        return '<!-- 图片输入区 -->' +
          '<div class="field" style="position: relative;">' +
            '<div class="port dh-image-input-port start-image-port" data-port-type="start" title="' + _t('dh_image_port', '连接图片节点') + '"></div>' +
            '<div class="label">' + _t('dh_image_label', '角色图片') + ' <span style="color: red;">*</span></div>' +
            '<input class="dh-image" type="file" accept="image/*" />' +
            '<button class="mini-btn dh-image-clear" type="button" style="margin-top:4px; display:none;">' + _t('dh_clear_btn', '清除') + '</button>' +
            '<div class="dh-image-preview" style="display:none; margin-top:4px;">' +
              '<img class="dh-image-thumb" style="max-width:100%; max-height:80px; border-radius:4px;" />' +
            '</div>' +
          '</div>' +
          '<!-- 音频输入区 -->' +
          '<div class="field" style="position: relative;">' +
            '<div class="port dh-audio-input-port audio-input-port" data-port-type="audio" title="' + _t('dh_audio_port', '连接音频节点') + '"></div>' +
            '<div class="label">' + _t('dh_audio_label', '说话音频') + ' <span style="color: red;">*</span></div>' +
            '<input class="dh-audio" type="file" accept="audio/*" />' +
            '<button class="mini-btn dh-audio-clear" type="button" style="margin-top:4px; display:none;">' + _t('dh_clear_btn', '清除') + '</button>' +
            '<div class="dh-audio-preview" style="display:none; margin-top:4px;">' +
              '<audio class="dh-audio-player" controls style="width:100%; max-height:32px;"></audio>' +
            '</div>' +
          '</div>' +
          '<!-- 提示词 -->' +
          '<div class="field">' +
            '<div class="label">' + _t('dh_prompt_label', '提示词') + ' <span style="color: red;">*</span></div>' +
            '<textarea class="dh-prompt" rows="2" placeholder="' + _t('dh_prompt_placeholder', '输入视频生成的提示词') + '"></textarea>' +
          '</div>' +
          '<!-- 生成按钮 -->' +
          '<div class="field">' +
            '<button class="gen-btn dh-generate-btn" type="button">' + _t('dh_generate_btn', '生成视频') + '</button>' +
            '<div class="gen-meta dh-status" style="display:none;"></div>' +
          '</div>' +
          '<!-- 视频结果 -->' +
          '<div class="field dh-result-field" style="display:none;">' +
            '<div class="label">' + _t('dh_result_label', '生成结果') + '</div>' +
            '<video class="dh-result-video" controls style="width:100%; border-radius:4px;"></video>' +
          '</div>';
      },
      onCreated: function(node, el) {
        var promptEl = el.querySelector('.dh-prompt');
        var imageEl = el.querySelector('.dh-image');
        var imagePreview = el.querySelector('.dh-image-preview');
        var imageThumb = el.querySelector('.dh-image-thumb');
        var imageClearBtn = el.querySelector('.dh-image-clear');
        var audioEl = el.querySelector('.dh-audio');
        var audioPreview = el.querySelector('.dh-audio-preview');
        var audioPlayer = el.querySelector('.dh-audio-player');
        var audioClearBtn = el.querySelector('.dh-audio-clear');
        var generateBtn = el.querySelector('.dh-generate-btn');
        var statusEl = el.querySelector('.dh-status');
        var resultField = el.querySelector('.dh-result-field');
        var resultVideo = el.querySelector('.dh-result-video');

        // 初始化：如果有已保存的图片URL，显示预览
        if (node.data.imageUrl) {
          imageThumb.src = typeof proxyDownloadUrl === 'function' ? proxyDownloadUrl(node.data.imageUrl) : node.data.imageUrl;
          imagePreview.style.display = 'block';
          imageClearBtn.style.display = 'inline-block';
        }

        // 初始化：如果有已保存的音频URL，显示播放器
        if (node.data.audioUrl) {
          audioPlayer.src = typeof proxyDownloadUrl === 'function' ? proxyDownloadUrl(node.data.audioUrl) : node.data.audioUrl;
          audioPreview.style.display = 'block';
          audioClearBtn.style.display = 'inline-block';
        }

        // 初始化：恢复视频结果
        if (node.data.videoUrl && resultVideo) {
          resultVideo.src = typeof proxyDownloadUrl === 'function' ? proxyDownloadUrl(node.data.videoUrl) : node.data.videoUrl;
          resultField.style.display = 'block';
        }

        // 初始化：恢复状态
        if (node.data.status && statusEl) {
          statusEl.style.display = 'block';
          if (node.data.status === 'SUCCESS') {
            statusEl.style.color = '#16a34a';
            statusEl.textContent = _t('dh_generate_success', '生成成功！');
          } else if (node.data.status === 'FAILED') {
            statusEl.style.color = '#dc2626';
            statusEl.textContent = _t('dh_generate_failed', '生成失败');
          }
        }

        // 提示词输入：设置默认值并监听变更
        promptEl.value = node.data.prompt || DEFAULT_PROMPT;
        promptEl.addEventListener('input', function() {
          node.data.prompt = promptEl.value;
        });

        // 图片上传
        imageEl.addEventListener('change', function() {
          var file = imageEl.files && imageEl.files[0];
          if (!file) return;
          node.data.imageFile = file;
          var localUrl = URL.createObjectURL(file);
          imageThumb.src = localUrl;
          imagePreview.style.display = 'block';
          imageClearBtn.style.display = 'inline-block';
        });

        // 清除图片
        imageClearBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          node.data.imageFile = null;
          node.data.imageUrl = '';
          node.data.imagePreview = '';
          imageThumb.removeAttribute('src');
          imagePreview.style.display = 'none';
          imageClearBtn.style.display = 'none';
          imageEl.value = '';
          // 断开图片连接
          state.imageConnections = state.imageConnections.filter(function(c) {
            return !(c.to === node.id && c.portType === 'start');
          });
          if (typeof renderAllConnections === 'function') renderAllConnections();
          safeAutoSave();
        });

        // 音频上传
        audioEl.addEventListener('change', function() {
          var file = audioEl.files && audioEl.files[0];
          if (!file) return;
          node.data.audioFile = file;
          var localUrl = URL.createObjectURL(file);
          audioPlayer.src = localUrl;
          audioPreview.style.display = 'block';
          audioClearBtn.style.display = 'inline-block';
        });

        // 清除音频
        audioClearBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          node.data.audioFile = null;
          node.data.audioUrl = '';
          audioPlayer.removeAttribute('src');
          audioPlayer.load();
          audioPreview.style.display = 'none';
          audioClearBtn.style.display = 'none';
          audioEl.value = '';
          // 断开音频连接
          state.audioConnections = (state.audioConnections || []).filter(function(c) {
            return c.to !== node.id;
          });
          if (typeof renderAllConnections === 'function') renderAllConnections();
          safeAutoSave();
        });

        // === 暴露方法供连接线回调使用 ===

        // 当图片节点通过连接线连接时调用
        node._onImageConnected = function(imageUrl, imagePreviewUrl) {
          node.data.imageUrl = imageUrl;
          node.data.imagePreview = imagePreviewUrl || imageUrl;
          imageThumb.src = typeof proxyDownloadUrl === 'function' ? proxyDownloadUrl(imagePreviewUrl || imageUrl) : (imagePreviewUrl || imageUrl);
          imagePreview.style.display = 'block';
          imageClearBtn.style.display = 'inline-block';
        };

        // 当音频节点通过连接线连接时调用
        node._onAudioConnected = function(audioUrl, audioName) {
          node.data.audioUrl = audioUrl;
          audioPlayer.src = typeof proxyDownloadUrl === 'function' ? proxyDownloadUrl(audioUrl) : audioUrl;
          audioPreview.style.display = 'block';
          audioClearBtn.style.display = 'inline-block';
        };

        // 生成视频按钮
        generateBtn.addEventListener('click', async function(e) {
          e.stopPropagation();

          // 验证输入
          if (!node.data.prompt || !node.data.prompt.trim()) {
            showToast(_t('dh_no_prompt_error', '请输入提示词'), 'warning');
            return;
          }
          if (!node.data.imageFile && !node.data.imageUrl) {
            showToast(_t('dh_no_image_error', '请上传角色图片或连接图片节点'), 'warning');
            return;
          }
          if (!node.data.audioFile && !node.data.audioUrl) {
            showToast(_t('dh_no_audio_error', '请上传说话音频或连接音频节点'), 'warning');
            return;
          }

          var userId = getUserId();
          if (!userId) {
            showToast(_t('dh_login_required', '请先登录后再使用数字人功能'), 'error');
            return;
          }

          try {
            setBtnLoading(generateBtn, _t('dh_generating', '生成中...'));
            statusEl.style.display = 'block';
            statusEl.style.color = '';
            statusEl.textContent = _t('dh_uploading_files', '正在上传文件...');
            resultField.style.display = 'none';

            // 上传图片（如果需要）
            var imageUrl = node.data.imageUrl;
            if (node.data.imageFile && !imageUrl) {
              imageUrl = await uploadFile(node.data.imageFile);
              if (!imageUrl) {
                throw new Error('图片上传失败');
              }
              node.data.imageUrl = imageUrl;
            }

            // 上传音频（如果需要）
            var audioUrl = node.data.audioUrl;
            if (node.data.audioFile && !audioUrl) {
              audioUrl = await uploadAudioFile(node.data.audioFile);
              if (!audioUrl) {
                throw new Error('音频上传失败');
              }
              node.data.audioUrl = audioUrl;
            }

            statusEl.textContent = _t('dh_submitting_task', '正在提交任务...');

            // 获取数字人任务ID
            var taskId = TaskConfig.getTaskIdByKey('digital_human_ltx2_3_voice', 'digital_human');
            if (!taskId) {
              taskId = TaskConfig.getTaskIdByKey('digital_human', 'digital_human');
            }
            if (!taskId) {
              throw new Error('未找到数字人任务配置');
            }

            // 提交任务
            var form = new FormData();
            form.append('image_urls', imageUrl);
            form.append('audio_urls', audioUrl);
            form.append('prompt', node.data.prompt);
            form.append('task_id', taskId);
            form.append('ratio', state.ratio || '9:16');
            form.append('duration_seconds', 5);
            form.append('count', 1);
            form.append('user_id', userId);

            var authToken = getAuthToken();
            if (authToken) {
              form.append('auth_token', authToken);
            }

            var res = await fetch('/api/ai-app-run-image', {
              method: 'POST',
              body: form
            });

            var data = await res.json();

            if (data.project_ids && data.project_ids.length > 0) {
              node.data.projectId = data.project_ids[0];
              statusEl.textContent = _t('dh_task_submitted', '任务已提交，正在生成视频...');

              pollVideoStatus(node.id, node);
            } else {
              throw new Error(data.detail || data.message || '提交任务失败');
            }

          } catch (error) {
            console.error('数字人视频生成失败:', error);
            statusEl.style.color = '#dc2626';
            statusEl.textContent = _t('dh_generate_failed', '生成失败') + ': ' + (error.message || '未知错误');
            setBtnReady(generateBtn, _t('dh_generate_btn', '生成视频'));
            showToast(_t('dh_generate_failed', '数字人视频生成失败'), 'error');
          }
        });

        // 轮询视频状态
        function pollVideoStatus(nodeId, node) {
          pollTaskStatus({
            statusUrl: '/api/video-status/' + node.data.projectId,
            onSuccess: function(payload) {
              if (payload.result_url) {
                node.data.videoUrl = payload.result_url;
                resultVideo.src = payload.result_url;
                resultField.style.display = 'block';
              }
              node.data.status = 'SUCCESS';
              statusEl.style.color = '#16a34a';
              statusEl.textContent = _t('dh_generate_success', '生成成功！');
              setBtnReady(generateBtn, _t('dh_generate_btn', '生成视频'));
              showToast(_t('dh_generate_success', '数字人视频生成成功'), 'success');
              safeAutoSave();
            },
            onFailed: function(payload) {
              node.data.status = 'FAILED';
              statusEl.style.color = '#dc2626';
              statusEl.textContent = _t('dh_generate_failed', '生成失败') + ': ' + (payload.reason || payload.message || '未知错误');
              setBtnReady(generateBtn, _t('dh_generate_btn', '生成视频'));
              showToast(_t('dh_generate_failed', '数字人视频生成失败'), 'error');
            },
            onTimeout: function() {
              node.data.status = 'TIMEOUT';
              statusEl.style.color = '#dc2626';
              statusEl.textContent = _t('dh_generate_timeout', '生成超时');
              setBtnReady(generateBtn, _t('dh_generate_btn', '生成视频'));
            }
          });
        }
      }
    }, opts);
  }

  var createDigitalHumanNodeWithData = createNodeWithDataFactory(
    createDigitalHumanNode,
    function(el, node) {
      // createNodeWithDataFactory 会调用 onCreated，
      // 在 onCreated 中已经处理了数据恢复，这里不需要额外处理
    }
  );

  // 注册到全局
  window.createDigitalHumanNode = createDigitalHumanNode;
  window.createDigitalHumanNodeWithData = createDigitalHumanNodeWithData;

  // ─── 注册输入端口（供连接系统自动发现）───
  registerInputPorts('digital_human', [
    PORT_PRESETS.IMAGE_INPUT({
      guard: function(n) { return !n.data.imageUrl; },
      onConnect: function(fromNode, targetNode) {
        targetNode.data.imageUrl = fromNode.data.url || '';
        targetNode.data.imagePreview = fromNode.data.preview || fromNode.data.url || '';
        if (typeof targetNode._onImageConnected === 'function') {
          targetNode._onImageConnected(fromNode.data.url, fromNode.data.preview || fromNode.data.url);
        }
      }
    }),
    PORT_PRESETS.AUDIO_INPUT({
      guard: function(n) { return !n.data.audioUrl; },
      onConnect: function(fromNode, targetNode) {
        targetNode.data.audioUrl = fromNode.data.url;
        if (typeof targetNode._onAudioConnected === 'function') {
          targetNode._onAudioConnected(fromNode.data.url, fromNode.data.name || '连接的音频');
        }
      }
    })
  ]);

  // 注册到节点注册表
  registerNodeType('digital_human', {
    createFn: createDigitalHumanNode,
    createWithDataFn: createDigitalHumanNodeWithData
  });

})();
