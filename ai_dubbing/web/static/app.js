document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('dubbing-form');
  const statusSection = document.getElementById('status-section');
  const statusTitle = document.getElementById('status-title');
  const statusMessage = document.getElementById('status-message');
  const progressContainer = document.getElementById('progress-container');
  const progressFill = document.getElementById('progress-fill');
  const progressText = document.getElementById('progress-text');
  const resultSection = document.getElementById('result-section');
  const downloadLink = document.getElementById('download-link');
  const submitBtn = document.getElementById('submit-btn');

  // Optimization status elements
  const optimizationStatusSection = document.getElementById('optimization-status-section');
  const optimizationStatusTitle = document.getElementById('optimization-status-title');
  const optimizationStatusMessage = document.getElementById('optimization-status-message');
  const optimizationProgressContainer = document.getElementById('optimization-progress-container');
  const optimizationProgressFill = document.getElementById('optimization-progress-fill');
  const optimizationProgressText = document.getElementById('optimization-progress-text');
  const optimizationResultSection = document.getElementById('optimization-result-section');
  const optimizationDownloadLink = document.getElementById('optimization-download-link');

  // Dubbing status elements
  const dubbingStatusSection = document.getElementById('dubbing-status-section');
  const dubbingStatusTitle = document.getElementById('dubbing-status-title');
  const dubbingStatusMessage = document.getElementById('dubbing-status-message');
  const dubbingProgressContainer = document.getElementById('dubbing-progress-container');
  const dubbingProgressFill = document.getElementById('dubbing-progress-fill');
  const dubbingProgressText = document.getElementById('dubbing-progress-text');
  const dubbingResultSection = document.getElementById('dubbing-result-section');
  const dubbingDownloadLink = document.getElementById('dubbing-download-link');

  // Subtitle optimization elements
  const optimizationForm = document.getElementById('optimization-form');
  const optimizeBtn = document.getElementById('optimize-btn');
  
  const engineSelect = document.getElementById('tts_engine');
  const strategySelect = document.getElementById('strategy');
  const languageSelect = document.getElementById('language');

  // File upload areas
  const uploadAreas = document.querySelectorAll('.file-upload-area');
  const fileInputs = document.querySelectorAll('.file-input');

  document.addEventListener('click', (e) => {
    if (e.target.closest('.file-upload-area') && e.target.tagName !== 'INPUT') {
      const uploadArea = e.target.closest('.file-upload-area');
      const input = uploadArea.querySelector('.file-input');
      if (input) {
        input.click();
      }
    }
  });

  // Voice pair management
  const voicePairsContainer = document.getElementById('voice-pairs-container');
  const addVoicePairBtn = document.getElementById('add-voice-pair-btn');
  let pairCount = 0;
  let currentTaskInterval = null; // 全局变量追踪当前任务的轮询interval

  function createVoicePair() {
    pairCount++;
    const pairDiv = document.createElement('div');
    pairDiv.classList.add('voice-pair');
    pairDiv.innerHTML = `
      <div class="file-upload-area" data-type="voice">
        <input type="file" name="voice_files" accept=".wav,.mp3" required class="file-input">
        <div class="upload-content">
          <i class="fas fa-cloud-upload-alt"></i>
          <p>选择语音文件</p>
          <span class="file-name">未选择</span>
        </div>
      </div>
      <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required></textarea>
      <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
    `;

    const input = pairDiv.querySelector('.file-input');
    const uploadArea = pairDiv.querySelector('.file-upload-area');
    
    input.addEventListener('change', (e) => handleFileSelection(e, uploadArea, 'voice'));
    
    const removeBtn = pairDiv.querySelector('.remove-pair-btn');
    removeBtn.addEventListener('click', () => {
      pairDiv.remove();
    });

    voicePairsContainer.appendChild(pairDiv);
  }

  addVoicePairBtn.addEventListener('click', createVoicePair);
  createVoicePair(); // Add the first pair initially

  // Initialize the application
  initApp();

  async function initApp() {
    await loadOptions();
    const basicConfig = await loadConfig();
    setupFileUploads();
    setupFormSubmission();
    setupOptimizationForm();
    setupFormValidation();
    setupTabs();
    setupMainTabs();
    setupPasswordToggle();
    // Populate voice pairs with config data if available
    if (basicConfig && basicConfig.voice_files && basicConfig.prompt_texts) {
      populateVoicePairsFromConfig(basicConfig);
    }
  }

  function populateVoicePairsFromConfig(basicConfig) {
    try {
      // Clear the initial empty voice pair if it hasn't been used
      const firstPair = voicePairsContainer.querySelector('.voice-pair');
      const firstVoiceInput = firstPair ? firstPair.querySelector('input[type="file"]') : null;
      const firstPrompt = firstPair ? firstPair.querySelector('textarea') : null;
      if (firstPair && voicePairsContainer.children.length === 1 && firstVoiceInput && firstVoiceInput.files.length === 0 && firstPrompt && firstPrompt.value.trim() === '') {
          voicePairsContainer.innerHTML = '';
      }

      const voiceFiles = basicConfig.voice_files.split(',').map(file => file.trim());
      const promptTexts = basicConfig.prompt_texts.split(',').map(text => text.trim());

      for (let i = 0; i < voiceFiles.length; i++) {
        if (i >= promptTexts.length) break;
        const pairDiv = document.createElement('div');
        pairDiv.classList.add('voice-pair');
        pairDiv.dataset.path = voiceFiles[i]; // Store original path

        pairDiv.innerHTML = `
          <div class="file-upload-area" data-type="voice">
            <input type="file" name="voice_files" accept=".wav,.mp3" class="file-input">
            <div class="upload-content">
              <i class="fas fa-check-circle" style="color: #10b981;"></i>
              <p>预设语音文件</p>
              <span class="file-name" style="color: #10b981;">${voiceFiles[i].split(/[\\/]/).pop()}</span>
            </div>
          </div>
          <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required>${promptTexts[i]}</textarea>
          <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
        `;

        const input = pairDiv.querySelector('.file-input');
        const uploadArea = pairDiv.querySelector('.file-upload-area');
        input.addEventListener('change', (e) => handleFileSelection(e, uploadArea, 'voice'));

        const removeBtn = pairDiv.querySelector('.remove-pair-btn');
        removeBtn.addEventListener('click', () => pairDiv.remove());

        voicePairsContainer.appendChild(pairDiv);
      }
    } catch (error) {
      console.error('Failed to populate voice pairs from config:', error);
    }
  }

  function setupPasswordToggle() {
    document.addEventListener('click', e => {
      if (e.target.classList.contains('toggle-password')) {
        const icon = e.target;
        const input = icon.previousElementSibling;
        if (input && input.tagName === 'INPUT') {
          if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
          } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
          }
        }
      }
    });
  }

  // Load options from server
  async function loadOptions() {
    try {
      showLoadingState();
      const response = await fetch('/dubbing/options');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      populateSelect(engineSelect, data.tts_engines || [], 'TTS 引擎', 'fish_speech');
      populateSelect(strategySelect, data.strategies || [], '策略', 'stretch');
      populateSelect(languageSelect, data.languages || [], '语言');
      
      hideLoadingState();
    } catch (error) {
      console.error('Failed to load options:', error);
      showError('加载配置选项失败，请刷新页面重试');
      hideLoadingState();
    }
  }

  function showLoadingState() {
    [engineSelect, strategySelect, languageSelect].forEach(select => {
      select.innerHTML = '<option value="">加载中...</option>';
      select.disabled = true;
    });
  }

  function hideLoadingState() {
    [engineSelect, strategySelect, languageSelect].forEach(select => {
      select.disabled = false;
    });
  }

  function populateSelect(select, options, placeholder, defaultValue = null) {
    select.innerHTML = '';
    
    // Add placeholder option
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = `选择${placeholder}`;
    placeholderOpt.disabled = true;
    select.appendChild(placeholderOpt);
    
    // Add options
    options.forEach(option => {
      const opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option;
      if (option === defaultValue) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  }

  function setupTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.dataset.tab;

        tabLinks.forEach(l => l.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));

        link.classList.add('active');
        document.getElementById(tabId).classList.add('active');
      });
    });
  }

  function setupMainTabs() {
    const mainTabLinks = document.querySelectorAll('.main-tab-link');
    const mainTabContents = document.querySelectorAll('.main-tab-content');

    mainTabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.dataset.tab;

        // Remove active class from all main tab links and contents
        mainTabLinks.forEach(l => l.classList.remove('active'));
        mainTabContents.forEach(c => c.classList.remove('active'));

        // Add active class to clicked link and corresponding content
        link.classList.add('active');
        const targetTab = document.getElementById(tabId);
        if (targetTab) {
          targetTab.classList.add('active');
        }

        // Log tab switch for debugging
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          console.log('切换到标签页:', tabId);
        }
      });
    });
  }

  // 统一的配置加载和设置函数
  function setConfigFieldValue(selector, value) {
    const field = document.querySelector(selector);
    if (field && value !== undefined && value !== null && value !== '') {
      field.value = value;
    }
  }

async function loadConfig() {
    try {
      const response = await fetch('/dubbing/config');
      const data = await response.json();
      
      // Set basic configuration values
      if (data.basic) {
        setConfigFieldValue('#tts_engine', data.basic.tts_engine);
        setConfigFieldValue('#strategy', data.basic.strategy);
      }

      // Set time borrowing configuration values in optimization tab
      if (data.time_borrowing) {
          setTimeout(() => {
          setConfigFieldValue('input[name="opt_min_gap_threshold"]', data.time_borrowing.min_gap_threshold);
          setConfigFieldValue('input[name="opt_borrow_ratio"]', data.time_borrowing.borrow_ratio);
          setConfigFieldValue('input[name="opt_extra_buffer"]', data.time_borrowing.extra_buffer);
          }, 100);
      }

      // Set subtitle optimization configuration values in optimization tab
      if (data.subtitle_optimization) {
          setTimeout(() => {
          setConfigFieldValue('input[name="opt_llm_api_key"]', data.subtitle_optimization.llm_api_key);
          setConfigFieldValue('input[name="opt_llm_model"]', data.subtitle_optimization.llm_model);
          setConfigFieldValue('input[name="opt_base_url"]', data.subtitle_optimization.base_url);
          setConfigFieldValue('input[name="opt_llm_max_concurrency"]', data.subtitle_optimization.llm_max_concurrency);
          setConfigFieldValue('input[name="opt_chinese_char_min_time"]', data.subtitle_optimization.chinese_char_min_time);
          setConfigFieldValue('input[name="opt_english_word_min_time"]', data.subtitle_optimization.english_word_min_time);
          setConfigFieldValue('input[name="opt_llm_max_retries"]', data.subtitle_optimization.llm_max_retries);
          setConfigFieldValue('input[name="opt_llm_timeout"]', data.subtitle_optimization.llm_timeout);
          }, 100);
      }

      // Populate concurrency tab content
      const concurrencyTab = document.getElementById('tab-concurrency');
      if (concurrencyTab && data.concurrency) {
      concurrencyTab.innerHTML = `
        <div class="options-row">
          <div class="form-group">
            <label class="form-label"><i class="fas fa-bolt"></i> TTS最大并发数</label>
            <input type="number" name="tts_max_concurrency" class="form-select" value="${data.concurrency.tts_max_concurrency}">
          </div>
          <div class="form-group">
            <label class="form-label"><i class="fas fa-redo"></i> TTS最大重试次数</label>
            <input type="number" name="tts_max_retries" class="form-select" value="${data.concurrency.tts_max_retries}">
          </div>
        </div>
      `;
      }

      return data.basic;
    } catch (error) {
      console.error('Failed to load config:', error);
      return null;
    }
  }

  // Get form configuration data for saving
  function getFormConfig() {
    return {
      concurrency: {
        tts_max_concurrency: document.querySelector('[name="tts_max_concurrency"]')?.value || '',
        tts_max_retries: document.querySelector('[name="tts_max_retries"]')?.value || '',
      },
      subtitle_optimization: {
        llm_api_key: document.querySelector('input[name="opt_llm_api_key"]')?.value || '',
        llm_model: document.querySelector('input[name="opt_llm_model"]')?.value || '',
        base_url: document.querySelector('input[name="opt_base_url"]')?.value || '',
        chinese_char_min_time: document.querySelector('input[name="opt_chinese_char_min_time"]')?.value || '',
        english_word_min_time: document.querySelector('input[name="opt_english_word_min_time"]')?.value || '',
        llm_max_concurrency: document.querySelector('input[name="opt_llm_max_concurrency"]')?.value || '',
        llm_max_retries: document.querySelector('input[name="opt_llm_max_retries"]')?.value || '',
        llm_timeout: document.querySelector('input[name="opt_llm_timeout"]')?.value || '',
      },
      time_borrowing: {
        min_gap_threshold: document.querySelector('input[name="opt_min_gap_threshold"]')?.value || '',
        borrow_ratio: document.querySelector('input[name="opt_borrow_ratio"]')?.value || '',
        extra_buffer: document.querySelector('input[name="opt_extra_buffer"]')?.value || '',
      }
    };
  }

  // Setup file upload functionality
  function setupFileUploads() {
    uploadAreas.forEach((area, index) => {
      const input = fileInputs[index];
      const fileType = area.dataset.type;
      
      // File selection change
      input.addEventListener('change', (e) => handleFileSelection(e, area, fileType));
      
      // Drag and drop
      area.addEventListener('dragover', handleDragOver);
      area.addEventListener('dragleave', handleDragLeave);
      area.addEventListener('drop', (e) => handleDrop(e, area, input, fileType));
      
      // Prevent default drag behaviors
      area.addEventListener('dragenter', (e) => e.preventDefault());
    });
  }

  function handleFileSelection(event, area, fileType) {
    const files = event.target.files;
    updateFileDisplay(area, files, fileType);
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
  }

  function handleDrop(e, area, input, fileType) {
    e.preventDefault();
    area.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    input.files = files;
    updateFileDisplay(area, files, fileType);
    validateForm();
  }

  function updateFileDisplay(area, files, fileType) {
    const fileNameSpan = area.querySelector('.file-name');
    const uploadContent = area.querySelector('.upload-content');
    
    if (files.length > 0) {
      if (fileType === 'voice' && files.length > 1) {
        fileNameSpan.textContent = `已选择 ${files.length} 个文件`;
        fileNameSpan.style.color = '#10b981';
      } else {
        fileNameSpan.textContent = files[0].name;
        fileNameSpan.style.color = '#10b981';
      }
      
      // Update icon and text
      uploadContent.innerHTML = `
        <i class="fas fa-check-circle" style="color: #10b981;"></i>
        <p>文件已选择</p>
        <span class="file-name" style="color: #10b981;">${fileNameSpan.textContent}</span>
      `;
    } else {
      fileNameSpan.textContent = '未选择文件';
      fileNameSpan.style.color = '#999';
      
      // Reset to default
      uploadContent.innerHTML = `
        <i class="fas fa-cloud-upload-alt"></i>
        <p>点击选择文件或拖拽到此处</p>
        <span class="file-name">未选择文件</span>
      `;
    }
  }

  // Setup form validation
  function setupFormValidation() {
    // Validation will now only run on submit
  }

  // Setup form submission
  function setupFormSubmission() {
    form.addEventListener('submit', handleFormSubmit);
  }

  // Setup optimization form
  function setupOptimizationForm() {
    if (optimizationForm) {
      optimizationForm.addEventListener('submit', handleOptimizationSubmit);
      
      // Setup file upload for optimization form
      const optimizationArea = optimizationForm.querySelector('.file-upload-area');
      const optimizationInput = optimizationForm.querySelector('.file-input');
      
      if (optimizationArea && optimizationInput) {
        optimizationInput.addEventListener('change', (e) => handleFileSelection(e, optimizationArea, 'optimization-srt'));
        optimizationArea.addEventListener('dragover', handleDragOver);
        optimizationArea.addEventListener('dragleave', handleDragLeave);
        optimizationArea.addEventListener('drop', (e) => handleDrop(e, optimizationArea, optimizationInput, 'optimization-srt'));
        optimizationArea.addEventListener('dragenter', (e) => e.preventDefault());
      }
    }
  }

  async function handleOptimizationSubmit(e) {
    e.preventDefault();
    
    const optimizationFile = optimizationForm.querySelector('input[name="input_file"]');
    
    if (!optimizationFile.files.length) {
      showError('请选择要优化的 SRT 文件');
      return;
    }

    // 检查文件类型
    const file = optimizationFile.files[0];
    if (!file.name.toLowerCase().endsWith('.srt')) {
      showError('仅支持 .srt 格式的字幕文件');
      return;
    }

    // 清理之前的任务状态
    cleanupOptimizationTask();
    
    showOptimizationStatus('准备中...', '正在保存配置并准备字幕优化...');
    optimizationStatusSection.style.display = 'block';
    setOptimizationLoading(true);
    
    try {
      // 首先保存字幕优化配置
      const configData = {
        concurrency: {
          tts_max_concurrency: document.querySelector('[name="tts_max_concurrency"]')?.value || '',
          tts_max_retries: document.querySelector('[name="tts_max_retries"]')?.value || '',
        },
        subtitle_optimization: {
          llm_api_key: document.querySelector('input[name="opt_llm_api_key"]')?.value || '',
          llm_model: document.querySelector('input[name="opt_llm_model"]')?.value || '',
          base_url: document.querySelector('input[name="opt_base_url"]')?.value || '',
          chinese_char_min_time: document.querySelector('input[name="opt_chinese_char_min_time"]')?.value || '',
          english_word_min_time: document.querySelector('input[name="opt_english_word_min_time"]')?.value || '',
          llm_max_concurrency: document.querySelector('input[name="opt_llm_max_concurrency"]')?.value || '',
          llm_max_retries: document.querySelector('input[name="opt_llm_max_retries"]')?.value || '',
          llm_timeout: document.querySelector('input[name="opt_llm_timeout"]')?.value || '',
        },
        time_borrowing: {
          min_gap_threshold: document.querySelector('input[name="opt_min_gap_threshold"]')?.value || '',
          borrow_ratio: document.querySelector('input[name="opt_borrow_ratio"]')?.value || '',
          extra_buffer: document.querySelector('input[name="opt_extra_buffer"]')?.value || '',
        }
      };

      // 保存配置
      await fetch('/dubbing/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(configData),
      });

      showOptimizationStatus('准备中...', '配置已保存，正在开始字幕优化...');

      const formData = new FormData();
      formData.append('input_file', file);

      const response = await fetch('/subtitle-optimization', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`请求失败: ${response.status} - ${errorText}`);
      }
      
      const result = await response.json();
      
      if (result.task_id) {
        pollTaskStatus(result.task_id, 'optimization');
      } else {
        showError('未能获取任务ID');
      }
      
    } catch (error) {
      console.error('Optimization error:', error);
      showOptimizationError(`字幕优化失败: ${error.message}`);
      setOptimizationLoading(false);
    }
  }

  function setOptimizationLoading(loading) {
    if (loading) {
      optimizeBtn.disabled = true;
      optimizeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>优化中...</span>';
    } else {
      optimizeBtn.disabled = false;
      optimizeBtn.innerHTML = '<i class="fas fa-magic"></i><span>开始优化</span>';
    }
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    // 清理之前的任务状态
    cleanupDubbingTask();
    
    showDubbingStatus('准备中...', '正在保存配置...');
    dubbingStatusSection.style.display = 'block';
    setFormLoading(true);
    
    try {
      // 自动保存配置 - 和字幕优化保持一致
      const configData = getFormConfig();
      try {
        const configResponse = await fetch('/dubbing/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(configData)
        });
        
        if (configResponse.ok) {
          showDubbingStatus('准备中...', '配置已保存，正在准备文件上传...');
        } else {
          console.warn('配置保存失败，但继续执行配音任务');
          showDubbingStatus('准备中...', '正在准备文件上传...');
        }
      } catch (configError) {
        console.warn('配置保存出错:', configError);
        showDubbingStatus('准备中...', '正在准备文件上传...');
      }
      const formData = new FormData();

      // Append standard fields
      const fieldsToAppend = ['tts_engine', 'strategy', 'language'];
      fieldsToAppend.forEach(id => formData.append(id, document.getElementById(id).value));

      // Append file input
      const inputFile = document.querySelector('input[name="input_file"]');
      if(inputFile.files.length > 0) {
        formData.append('input_file', inputFile.files[0]);
      }

      // Append advanced config inputs
      const configInputs = document.querySelectorAll('#tab-concurrency input');
      configInputs.forEach(input => formData.append(input.name, input.value));

      // Handle voice pairs
      const voicePairs = document.querySelectorAll('.voice-pair');
      voicePairs.forEach(pair => {
        const fileInput = pair.querySelector('input[type="file"]');
        const promptText = pair.querySelector('textarea').value;
        const originalPath = pair.dataset.path || '';

        // Only add pairs that have either a new file or a pre-filled path and text
        if ((fileInput.files.length > 0 || originalPath) && promptText) {
            if (fileInput.files.length > 0) {
                formData.append('voice_files', fileInput.files[0]);
                formData.append('voice_files_paths', ''); // Placeholder
            } else if (originalPath) {
                formData.append('voice_files', new Blob(), ''); // Empty file placeholder
                formData.append('voice_files_paths', originalPath);
            }
            formData.append('prompt_texts', promptText);
        }
      });

      const response = await fetch('/dubbing', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`请求失败: ${response.status} - ${errorText}`);
      }
      
      const result = await response.json();
      
      if (result.task_id) {
        pollTaskStatus(result.task_id);
      } else {
        showError('未能获取任务ID');
      }
      
    } catch (error) {
      console.error('Submission error:', error);
      showDubbingError(`配音失败: ${error.message}`);
      setFormLoading(false);
    }
  }

  async function pollTaskStatus(taskId, taskType = 'dubbing') {
    if (taskType === 'optimization') {
      showOptimizationProgress();
    } else {
      showDubbingProgress();
    }
    
    // 根据任务类型确定状态查询URL
    const statusUrl = taskType === 'optimization' 
      ? `/subtitle-optimization/status/${taskId}` 
      : `/dubbing/status/${taskId}`;
    
    // 定义状态检查函数
    const checkStatus = async () => {
      try {
        const response = await fetch(statusUrl);
        if (!response.ok) {
          throw new Error('无法获取任务状态');
        }
        
        const data = await response.json();
        
        // 只在开发模式下显示详细日志
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          console.log('任务状态更新:', { 
            taskId, 
            taskType,
            status: data.status, 
            progress: data.progress, 
            message: data.message 
          });
        }
        
        // 根据任务类型更新状态
        if (taskType === 'optimization') {
          optimizationStatusTitle.textContent = '字幕优化中...';
          optimizationStatusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
          updateOptimizationProgress(data.progress);
        } else {
          dubbingStatusTitle.textContent = '配音处理中...';
          dubbingStatusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
          updateDubbingProgress(data.progress);
        }
        
        if (data.status === 'completed') {
          if (currentTaskInterval) {
            clearInterval(currentTaskInterval);
            currentTaskInterval = null;
          }
          // 根据任务类型显示结果
          if (taskType === 'optimization') {
            showOptimizationResult(data.result_url);
            setOptimizationLoading(false);
          } else {
            showDubbingResult(data.result_url);
            setFormLoading(false);
          }
          return true; // 任务完成
        } else if (data.status === 'failed') {
          if (currentTaskInterval) {
            clearInterval(currentTaskInterval);
            currentTaskInterval = null;
          }
          if (taskType === 'optimization') {
            showOptimizationError(`字幕优化失败: ${data.error || '未知错误'}`);
            setOptimizationLoading(false);
          } else {
            showDubbingError(`配音失败: ${data.error || '未知错误'}`);
            setFormLoading(false);
          }
          return true; // 任务失败
        }
        return false; // 继续轮询
      } catch (error) {
        console.error('Polling error:', error);
        if (currentTaskInterval) {
          clearInterval(currentTaskInterval);
          currentTaskInterval = null;
        }
        if (taskType === 'optimization') {
          showOptimizationError('无法轮询任务状态');
          setOptimizationLoading(false);
        } else {
          showDubbingError('无法轮询任务状态');
          setFormLoading(false);
        }
        return true; // 停止轮询
      }
    };
    
    // 立即执行第一次检查，避免等待轮询间隔
    if (await checkStatus()) {
      return; // 任务已完成或失败，无需轮询
    }
    
    // 设置高频轮询以捕获快速状态变化 (500ms间隔)
    currentTaskInterval = setInterval(async () => {
      if (await checkStatus()) {
        if (currentTaskInterval) {
          clearInterval(currentTaskInterval);
          currentTaskInterval = null;
        }
      }
    }, 500);
  }

  function updateProgress(progress) {
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${Math.round(progress)}%`;
  }

  function cleanupPreviousTask() {
    // 清理之前的轮询interval
    if (currentTaskInterval) {
      clearInterval(currentTaskInterval);
      currentTaskInterval = null;
    }
    
    // 重置状态界面元素的显示状态
    statusTitle.style.display = '';
    statusMessage.style.display = '';
    const statusIcon = document.querySelector('.status-icon');
    if (statusIcon) {
      statusIcon.style.display = '';
    }
    
    // 重置进度条
    updateProgress(0);
    
    // 隐藏结果区域
    resultSection.style.display = 'none';
    progressContainer.style.display = 'none';
    
    // 重置按钮状态
    setFormLoading(false);
  }

  function validateForm() {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    // Reset all error states
    form.querySelectorAll('.error-field').forEach(field => {
      field.classList.remove('error-field');
      field.style.borderColor = '';
    });
    
    requiredFields.forEach(field => {
      const hasValue = field.type === 'file' ? field.files.length > 0 : field.value.trim() !== '';
      
      if (!hasValue) {
        isValid = false;
        field.classList.add('error-field');
        field.style.borderColor = '#ef4444';
        
        // Add error animation
        field.style.animation = 'shake 0.5s ease-in-out';
        setTimeout(() => {
          field.style.animation = '';
        }, 500);
      }
    });
    
    // Validate file types
    const srtInput = document.querySelector('input[name="input_file"]');
    const voiceInput = document.querySelector('input[name="voice_files"]');
    
    if (srtInput.files.length > 0) {
      const file = srtInput.files[0];
      const allowedTypes = ['.srt', '.txt'];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      
      if (!allowedTypes.includes(fileExtension)) {
        isValid = false;
        showDubbingError(`不支持的文件格式: ${fileExtension}。请选择 .srt 或 .txt 文件。`);
        return false;
      }
    }
    
    if (voiceInput && voiceInput.files.length > 0) {
      for (let file of voiceInput.files) {
        const allowedTypes = ['.wav', '.mp3'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExtension)) {
          isValid = false;
          showDubbingError(`不支持的音频格式: ${fileExtension}。请选择 .wav 或 .mp3 文件。`);
          return false;
        }
      }
    }
    
    if (!isValid) {
      showDubbingError('请填写所有必填字段');
    }
    
    return isValid;
  }

  function setFormLoading(loading) {
    if (loading) {
      form.classList.add('loading');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>处理中...</span>';
    } else {
      form.classList.remove('loading');
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fas fa-play"></i><span>开始配音</span>';
    }
  }

  function showStatus(title, message) {
    statusTitle.textContent = title;
    statusMessage.textContent = message;
    progressContainer.style.display = 'none';
    resultSection.style.display = 'none';
  }

  function showOptimizationStatus(title, message) {
    optimizationStatusTitle.textContent = title;
    optimizationStatusMessage.textContent = message;
    optimizationProgressContainer.style.display = 'none';
    optimizationResultSection.style.display = 'none';
  }

  function showOptimizationProgress() {
    showOptimizationStatus('字幕优化中...', '正在处理字幕优化...');
    optimizationProgressContainer.style.display = 'block';
  }

  function updateOptimizationProgress(progress) {
    optimizationProgressFill.style.width = `${progress}%`;
    optimizationProgressText.textContent = `${Math.round(progress)}%`;
  }

  function showOptimizationResult(resultUrl) {
    const fileName = resultUrl.split('/').pop();
    
    // 添加CSS类来隐藏状态内容
    optimizationStatusSection.classList.add('show-result');
    
    // 设置下载链接
    optimizationDownloadLink.href = resultUrl;
    optimizationDownloadLink.download = fileName;
    
    // 显示结果区域，隐藏进度条
    optimizationResultSection.style.display = 'block';
    optimizationProgressContainer.style.display = 'none';
    
    // Add success animation
    optimizationResultSection.classList.add('success-animation');
    setTimeout(() => {
      optimizationResultSection.classList.remove('success-animation');
    }, 600);
  }

  function cleanupOptimizationTask() {
    // 清理之前的轮询interval
    if (currentTaskInterval) {
      clearInterval(currentTaskInterval);
      currentTaskInterval = null;
    }
    
    // 移除结果显示类
    optimizationStatusSection.classList.remove('show-result');
    
    // 重置状态界面元素的显示状态
    optimizationStatusTitle.style.display = '';
    optimizationStatusMessage.style.display = '';
    const statusIcon = optimizationStatusSection.querySelector('.status-icon');
    if (statusIcon) {
      statusIcon.style.display = '';
    }
    
    // 重置进度条
    updateOptimizationProgress(0);
    
    // 隐藏结果区域
    optimizationResultSection.style.display = 'none';
    optimizationProgressContainer.style.display = 'none';
    
    // 隐藏整个状态区域
    optimizationStatusSection.style.display = 'none';
    
    // 重置按钮状态
    setOptimizationLoading(false);
  }

  // Dubbing status functions
  function showDubbingStatus(title, message) {
    dubbingStatusTitle.textContent = title;
    dubbingStatusMessage.textContent = message;
    dubbingProgressContainer.style.display = 'none';
    dubbingResultSection.style.display = 'none';
  }

  function showDubbingProgress() {
    showDubbingStatus('配音处理中...', '正在处理配音...');
    dubbingProgressContainer.style.display = 'block';
  }

  function updateDubbingProgress(progress) {
    dubbingProgressFill.style.width = `${progress}%`;
    dubbingProgressText.textContent = `${Math.round(progress)}%`;
  }

  function showDubbingResult(resultUrl) {
    const fileName = resultUrl.split('/').pop();
    
    // 添加CSS类来隐藏状态内容
    dubbingStatusSection.classList.add('show-result');
    
    // 设置下载链接
    dubbingDownloadLink.href = resultUrl;
    dubbingDownloadLink.download = fileName;
    
    // 显示结果区域，隐藏进度条
    dubbingResultSection.style.display = 'block';
    dubbingProgressContainer.style.display = 'none';
    
    // Add success animation
    dubbingResultSection.classList.add('success-animation');
    setTimeout(() => {
      dubbingResultSection.classList.remove('success-animation');
    }, 600);
  }

  function cleanupDubbingTask() {
    // 清理之前的轮询interval
    if (currentTaskInterval) {
      clearInterval(currentTaskInterval);
      currentTaskInterval = null;
    }
    
    // 移除结果显示类
    dubbingStatusSection.classList.remove('show-result');
    
    // 重置状态界面元素的显示状态
    dubbingStatusTitle.style.display = '';
    dubbingStatusMessage.style.display = '';
    const statusIcon = dubbingStatusSection.querySelector('.status-icon');
    if (statusIcon) {
      statusIcon.style.display = '';
    }
    
    // 重置进度条
    updateDubbingProgress(0);
    
    // 隐藏结果区域
    dubbingResultSection.style.display = 'none';
    dubbingProgressContainer.style.display = 'none';
    
    // 隐藏整个状态区域
    dubbingStatusSection.style.display = 'none';
    
    // 重置按钮状态
    setFormLoading(false);
  }

  function showDubbingError(message) {
    showDubbingStatus('配音失败', message);
    dubbingProgressContainer.style.display = 'none';
    
    // Show error in dubbing status section
    dubbingStatusSection.style.display = 'block';
    
    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (dubbingStatusTitle.textContent === '配音失败') {
        dubbingStatusSection.style.display = 'none';
      }
    }, 8000);
  }

  function showProgress() {
    showStatus('处理中...', '正在上传文件并开始配音处理...');
    progressContainer.style.display = 'block';
  }

  function showResult(resultUrl) {
    // 只处理配音结果
    const fileName = resultUrl.split('/').pop();
    
    statusTitle.textContent = '配音完成';
    statusMessage.textContent = '您的配音文件已准备就绪，可以下载了！';
    
    // 更新结果区域的文本
    const resultTitle = resultSection.querySelector('h3');
    const resultDesc = resultSection.querySelector('p');
    if (resultTitle) resultTitle.textContent = '配音完成！';
    if (resultDesc) resultDesc.textContent = '您的配音文件已准备就绪';
    
    // 隐藏加载图标
    const statusIcon = document.querySelector('.status-icon');
    if (statusIcon) {
      statusIcon.style.display = 'none';
    }

    downloadLink.href = resultUrl;
    downloadLink.download = fileName;
    resultSection.style.display = 'block';
    progressContainer.style.display = 'none';
    
    // Add success animation
    resultSection.classList.add('success-animation');
    setTimeout(() => {
      resultSection.classList.remove('success-animation');
    }, 600);
  }

  function showSuccess(message) {
    showStatus('完成', message);
    progressContainer.style.display = 'none';
  }

  function showError(message) {
    showStatus('错误', message);
    progressContainer.style.display = 'none';
    
    // Show error in status section
    statusSection.style.display = 'block';
    
    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (statusTitle.textContent === '错误') {
        statusSection.style.display = 'none';
      }
    }, 8000);
  }

  function showOptimizationError(message) {
    showOptimizationStatus('优化失败', message);
    optimizationProgressContainer.style.display = 'none';
    
    // Show error in optimization status section
    optimizationStatusSection.style.display = 'block';
    
    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (optimizationStatusTitle.textContent === '优化失败') {
        optimizationStatusSection.style.display = 'none';
      }
    }, 8000);
  }

  // Add some interactive effects
  document.addEventListener('DOMContentLoaded', () => {
    // Add hover effects to form elements
    const formElements = document.querySelectorAll('.form-textarea, .form-select');
    formElements.forEach(element => {
      element.addEventListener('focus', () => {
        element.parentElement.style.transform = 'scale(1.02)';
      });
      
      element.addEventListener('blur', () => {
        element.parentElement.style.transform = 'scale(1)';
      });
    });
  });
});

// Add shake animation and error styles via CSS
const style = document.createElement('style');
style.textContent = `
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-5px); }
    75% { transform: translateX(5px); }
  }
  
  .error-field {
    border-color: #ef4444 !important;
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1) !important;
  }
`;
document.head.appendChild(style);