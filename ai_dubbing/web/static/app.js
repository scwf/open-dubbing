/**
 * AI Dubbing Web Application
 * Main application logic and UI management
 */

// Application Constants
const API_ENDPOINTS = {
  DUBBING: '/dubbing',
  OPTIONS: '/dubbing/options',
  CONFIG: '/dubbing/config',
  STATUS: '/dubbing/status'
};

const DEFAULT_VALUES = {
  TTS_ENGINE: 'fish_speech',
  STRATEGY: 'stretch',
  LANGUAGE: 'zh'
};

const FILE_TYPES = {
  INPUT: ['.srt', '.txt'],
  VOICE: ['.wav', '.mp3']
};

const POLLING_INTERVAL = 2000;

/**
 * Configuration Manager - handles loading and saving application configuration
 */
class ConfigManager {
  constructor() {
    this.config = null;
  }

  async loadOptions() {
    try {
      const response = await fetch(API_ENDPOINTS.OPTIONS);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to load options:', error);
      throw new Error('加载配置选项失败，请刷新页面重试');
    }
  }

  async loadConfig() {
    try {
      const response = await fetch(API_ENDPOINTS.CONFIG);
      const data = await response.json();
      this.config = data;
      return data;
    } catch (error) {
      console.error('Failed to load config:', error);
      return null;
    }
  }

  async saveConfig(configData) {
    try {
      const response = await fetch(API_ENDPOINTS.CONFIG, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configData),
      });
      
      if (!response.ok) {
        throw new Error('Configuration save failed');
      }
      
      return { success: true };
    } catch (error) {
      console.error('Failed to save config:', error);
      throw new Error('配置保存失败！');
    }
  }

  getConfigValue(section, key, fallback = '') {
    return this.config?.[section]?.[key] || fallback;
  }
}

/**
 * UI Manager - handles all UI interactions and updates
 */
class UIManager {
  constructor() {
    this.elements = this.initializeElements();
    this.setupEventListeners();
  }

  initializeElements() {
    return {
      form: document.getElementById('dubbing-form'),
      statusSection: document.getElementById('status-section'),
      statusTitle: document.getElementById('status-title'),
      statusMessage: document.getElementById('status-message'),
      progressContainer: document.getElementById('progress-container'),
      progressFill: document.getElementById('progress-fill'),
      progressText: document.getElementById('progress-text'),
      resultSection: document.getElementById('result-section'),
      downloadLink: document.getElementById('download-link'),
      submitBtn: document.getElementById('submit-btn'),
      engineSelect: document.getElementById('tts_engine'),
      strategySelect: document.getElementById('strategy'),
      languageSelect: document.getElementById('language'),
      saveConfigBtn: document.getElementById('save-config-btn')
    };
  }

  setupEventListeners() {
    this.setupTabNavigation();
    this.setupPasswordToggle();
    this.setupFormSubmission();
    this.setupFileUploads();
    this.setupConfigSaving();
  }

  setupTabNavigation() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.dataset.tab;
        
        // Remove active class from all elements
        tabLinks.forEach(l => l.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        
        // Add active class to selected elements
        link.classList.add('active');
        document.getElementById(tabId).classList.add('active');
      });
    });
  }

  setupPasswordToggle() {
    document.addEventListener('click', e => {
      if (e.target.classList.contains('toggle-password')) {
        this.togglePasswordVisibility(e.target);
      }
    });
  }

  togglePasswordVisibility(icon) {
    const input = icon.previousElementSibling;
    if (input && input.tagName === 'INPUT') {
      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';
      icon.classList.toggle('fa-eye', !isPassword);
      icon.classList.toggle('fa-eye-slash', isPassword);
    }
  }

  setupFormSubmission() {
    this.elements.form.addEventListener('submit', (e) => {
      e.preventDefault();
      window.app.dubbingService.handleFormSubmit();
    });
  }

  setupFileUploads() {
    const uploadAreas = document.querySelectorAll('.file-upload-area');
    const fileInputs = document.querySelectorAll('.file-input');

    // Global click handler for upload areas
    document.addEventListener('click', (e) => {
      if (e.target.closest('.file-upload-area') && e.target.tagName !== 'INPUT') {
        const uploadArea = e.target.closest('.file-upload-area');
        const input = uploadArea.querySelector('.file-input');
        if (input) input.click();
      }
    });

    uploadAreas.forEach((area, index) => {
      const input = fileInputs[index];
      const fileType = area.dataset.type;
      
      if (input) {
        input.addEventListener('change', (e) => this.handleFileSelection(e, area, fileType));
        this.setupDragAndDrop(area, input, fileType);
      }
    });
  }

  setupDragAndDrop(area, input, fileType) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      area.addEventListener(eventName, e => e.preventDefault());
    });

    area.addEventListener('dragover', () => area.classList.add('dragover'));
    area.addEventListener('dragleave', () => area.classList.remove('dragover'));
    area.addEventListener('drop', (e) => {
      area.classList.remove('dragover');
      const files = e.dataTransfer.files;
      input.files = files;
      this.handleFileSelection({ target: input }, area, fileType);
    });
  }

  handleFileSelection(event, area, fileType) {
    const files = event.target.files;
    this.updateFileDisplay(area, files, fileType);
  }

  updateFileDisplay(area, files, fileType) {
    const uploadContent = area.querySelector('.upload-content');
    
    if (files.length > 0) {
      const fileName = fileType === 'voice' && files.length > 1 
        ? `已选择 ${files.length} 个文件`
        : files[0].name;

      uploadContent.innerHTML = `
        <i class="fas fa-check-circle" style="color: #10b981;"></i>
        <p>文件已选择</p>
        <span class="file-name" style="color: #10b981;">${fileName}</span>
      `;
    } else {
      uploadContent.innerHTML = `
        <i class="fas fa-cloud-upload-alt"></i>
        <p>点击选择文件或拖拽到此处</p>
        <span class="file-name">未选择文件</span>
      `;
    }
  }

  setupConfigSaving() {
    this.elements.saveConfigBtn.addEventListener('click', () => {
      window.app.configManager.saveConfigFromForm();
    });
  }

  populateSelect(select, options, placeholder, defaultValue = null) {
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

  showLoadingState() {
    [this.elements.engineSelect, this.elements.strategySelect, this.elements.languageSelect]
      .forEach(select => {
        select.innerHTML = '<option value="">加载中...</option>';
        select.disabled = true;
      });
  }

  hideLoadingState() {
    [this.elements.engineSelect, this.elements.strategySelect, this.elements.languageSelect]
      .forEach(select => {
        select.disabled = false;
      });
  }

  setFormLoading(loading) {
    if (loading) {
      this.elements.form.classList.add('loading');
      this.elements.submitBtn.disabled = true;
      this.elements.submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>处理中...</span>';
    } else {
      this.elements.form.classList.remove('loading');
      this.elements.submitBtn.disabled = false;
      this.elements.submitBtn.innerHTML = '<i class="fas fa-play"></i><span>开始配音</span>';
    }
  }

  showStatus(title, message) {
    this.elements.statusTitle.textContent = title;
    this.elements.statusMessage.textContent = message;
    this.elements.progressContainer.style.display = 'none';
    this.elements.resultSection.style.display = 'none';
    this.elements.statusSection.style.display = 'block';
  }

  showProgress() {
    this.showStatus('处理中...', '正在上传文件并开始配音处理...');
    this.elements.progressContainer.style.display = 'block';
  }

  updateProgress(progress) {
    this.elements.progressFill.style.width = `${progress}%`;
    this.elements.progressText.textContent = `${Math.round(progress)}%`;
  }

  showResult(resultUrl) {
    this.elements.statusTitle.style.display = 'none';
    this.elements.statusMessage.style.display = 'none';
    document.querySelector('.status-icon').style.display = 'none';

    this.elements.downloadLink.href = resultUrl;
    this.elements.downloadLink.download = resultUrl.split('/').pop();
    this.elements.resultSection.style.display = 'block';
    this.elements.progressContainer.style.display = 'none';
    
    // Add success animation
    this.elements.resultSection.classList.add('success-animation');
    setTimeout(() => {
      this.elements.resultSection.classList.remove('success-animation');
    }, 600);
  }

  showError(message) {
    this.showStatus('错误', message);
    this.elements.progressContainer.style.display = 'none';
    
    // Auto-hide after 8 seconds
    setTimeout(() => {
      if (this.elements.statusTitle.textContent === '错误') {
        this.elements.statusSection.style.display = 'none';
      }
    }, 8000);
  }
}

/**
 * Voice Pair Manager - handles dynamic voice file and prompt pairs
 */
class VoicePairManager {
  constructor() {
    this.container = document.getElementById('voice-pairs-container');
    this.addButton = document.getElementById('add-voice-pair-btn');
    this.pairCount = 0;
    
    this.setupEventListeners();
    this.createInitialPair();
  }

  setupEventListeners() {
    this.addButton.addEventListener('click', () => this.createVoicePair());
  }

  createInitialPair() {
    this.createVoicePair();
  }

  createVoicePair() {
    this.pairCount++;
    const pairDiv = document.createElement('div');
    pairDiv.classList.add('voice-pair');
    pairDiv.innerHTML = this.getVoicePairHTML();

    this.attachPairEventListeners(pairDiv);
    this.container.appendChild(pairDiv);
  }

  getVoicePairHTML() {
    return `
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
  }

  attachPairEventListeners(pairDiv) {
    const input = pairDiv.querySelector('.file-input');
    const uploadArea = pairDiv.querySelector('.file-upload-area');
    const removeBtn = pairDiv.querySelector('.remove-pair-btn');
    
    input.addEventListener('change', (e) => 
      window.app.uiManager.handleFileSelection(e, uploadArea, 'voice')
    );
    
    removeBtn.addEventListener('click', () => pairDiv.remove());
  }

  populateFromConfig(basicConfig) {
    if (!basicConfig?.voice_files || !basicConfig?.prompt_texts) return;

    try {
      // Clear existing pairs except first if empty
      this.clearEmptyInitialPair();

      const voiceFiles = basicConfig.voice_files.split(',').map(file => file.trim());
      const promptTexts = basicConfig.prompt_texts.split(',').map(text => text.trim());

      for (let i = 0; i < voiceFiles.length && i < promptTexts.length; i++) {
        this.createPrefilledPair(voiceFiles[i], promptTexts[i]);
      }
    } catch (error) {
      console.error('Failed to populate voice pairs from config:', error);
    }
  }

  clearEmptyInitialPair() {
    const firstPair = this.container.querySelector('.voice-pair');
    if (firstPair && this.container.children.length === 1) {
      const firstVoiceInput = firstPair.querySelector('input[type="file"]');
      const firstPrompt = firstPair.querySelector('textarea');
      
      if (firstVoiceInput?.files.length === 0 && firstPrompt?.value.trim() === '') {
        this.container.innerHTML = '';
      }
    }
  }

  createPrefilledPair(voiceFile, promptText) {
    const pairDiv = document.createElement('div');
    pairDiv.classList.add('voice-pair');
    pairDiv.dataset.path = voiceFile;

    pairDiv.innerHTML = `
      <div class="file-upload-area" data-type="voice">
        <input type="file" name="voice_files" accept=".wav,.mp3" class="file-input">
        <div class="upload-content">
          <i class="fas fa-check-circle" style="color: #10b981;"></i>
          <p>预设语音文件</p>
          <span class="file-name" style="color: #10b981;">${voiceFile.split(/[\\/]/).pop()}</span>
        </div>
      </div>
      <textarea name="prompt_texts" placeholder="输入参考文本..." class="form-textarea" required>${promptText}</textarea>
      <button type="button" class="remove-pair-btn"><i class="fas fa-trash"></i></button>
    `;

    this.attachPairEventListeners(pairDiv);
    this.container.appendChild(pairDiv);
  }
}

/**
 * Form Validator - handles form validation logic
 */
class FormValidator {
  validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    // Reset error states
    this.resetErrorStates(form);
    
    // Check required fields
    requiredFields.forEach(field => {
      const hasValue = field.type === 'file' ? field.files.length > 0 : field.value.trim() !== '';
      
      if (!hasValue) {
        isValid = false;
        this.markFieldAsError(field);
      }
    });
    
    // Validate file types
    isValid = this.validateFileTypes(form) && isValid;
    
    if (!isValid) {
      window.app.uiManager.showError('请填写所有必填字段');
    }
    
    return isValid;
  }

  resetErrorStates(form) {
    form.querySelectorAll('.error-field').forEach(field => {
      field.classList.remove('error-field');
      field.style.borderColor = '';
    });
  }

  markFieldAsError(field) {
    field.classList.add('error-field');
    field.style.borderColor = '#ef4444';
    
    // Add shake animation
    field.style.animation = 'shake 0.5s ease-in-out';
    setTimeout(() => {
      field.style.animation = '';
    }, 500);
  }

  validateFileTypes(form) {
    const srtInput = form.querySelector('input[name="input_file"]');
    const voiceInputs = form.querySelectorAll('input[name="voice_files"]');
    
    // Validate input file
    if (srtInput?.files.length > 0) {
      const file = srtInput.files[0];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      
      if (!FILE_TYPES.INPUT.includes(fileExtension)) {
        window.app.uiManager.showError(
          `不支持的文件格式: ${fileExtension}。请选择 ${FILE_TYPES.INPUT.join(' 或 ')} 文件。`
        );
        return false;
      }
    }
    
    // Validate voice files
    for (const voiceInput of voiceInputs) {
      if (voiceInput.files.length > 0) {
        for (const file of voiceInput.files) {
          const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
          
          if (!FILE_TYPES.VOICE.includes(fileExtension)) {
            window.app.uiManager.showError(
              `不支持的音频格式: ${fileExtension}。请选择 ${FILE_TYPES.VOICE.join(' 或 ')} 文件。`
            );
            return false;
          }
        }
      }
    }
    
    return true;
  }
}

/**
 * Dubbing Service - handles dubbing process and status polling
 */
class DubbingService {
  constructor() {
    this.validator = new FormValidator();
    this.pollingInterval = null;
  }

  async handleFormSubmit() {
    if (!this.validator.validateForm(window.app.uiManager.elements.form)) {
      return;
    }

    window.app.uiManager.showStatus('准备中...', '正在准备文件上传...');
    window.app.uiManager.setFormLoading(true);
    
    try {
      const formData = this.buildFormData();
      const response = await fetch(API_ENDPOINTS.DUBBING, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`请求失败: ${response.status} - ${errorText}`);
      }
      
      const result = await response.json();
      
      if (result.task_id) {
        this.startPolling(result.task_id);
      } else {
        throw new Error('未能获取任务ID');
      }
      
    } catch (error) {
      console.error('Submission error:', error);
      window.app.uiManager.showError(`处理失败: ${error.message}`);
      window.app.uiManager.setFormLoading(false);
    }
  }

  buildFormData() {
    const form = window.app.uiManager.elements.form;
    const formData = new FormData();

    // Append standard fields
    const fieldsToAppend = ['tts_engine', 'strategy', 'language'];
    fieldsToAppend.forEach(id => {
      const element = document.getElementById(id);
      if (element) {
        formData.append(id, element.value);
      }
    });

    // Append input file
    const inputFile = form.querySelector('input[name="input_file"]');
    if (inputFile?.files.length > 0) {
      formData.append('input_file', inputFile.files[0]);
    }

    // Append config inputs
    const configInputs = form.querySelectorAll('#tab-concurrency input, #tab-subtitle input, #tab-time input');
    configInputs.forEach(input => {
      if (input.name) {
        formData.append(input.name, input.value);
      }
    });

    // Handle voice pairs
    this.appendVoicePairs(formData);

    return formData;
  }

  appendVoicePairs(formData) {
    const voicePairs = document.querySelectorAll('.voice-pair');
    
    voicePairs.forEach(pair => {
      const fileInput = pair.querySelector('input[type="file"]');
      const promptText = pair.querySelector('textarea').value;
      const originalPath = pair.dataset.path || '';

      if ((fileInput.files.length > 0 || originalPath) && promptText) {
        if (fileInput.files.length > 0) {
          formData.append('voice_files', fileInput.files[0]);
          formData.append('voice_files_paths', '');
        } else if (originalPath) {
          formData.append('voice_files', new Blob(), '');
          formData.append('voice_files_paths', originalPath);
        }
        formData.append('prompt_texts', promptText);
      }
    });
  }

  startPolling(taskId) {
    window.app.uiManager.showProgress();
    
    this.pollingInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API_ENDPOINTS.STATUS}/${taskId}`);
        if (!response.ok) {
          throw new Error('无法获取任务状态');
        }
        
        const data = await response.json();
        this.handlePollingResponse(data);
        
      } catch (error) {
        console.error('Polling error:', error);
        this.stopPolling();
        window.app.uiManager.showError('无法轮询任务状态');
        window.app.uiManager.setFormLoading(false);
      }
    }, POLLING_INTERVAL);
  }

  handlePollingResponse(data) {
    window.app.uiManager.elements.statusTitle.textContent = "处理中...";
    window.app.uiManager.elements.statusMessage.textContent = data.message || `当前进度: ${data.progress}%`;
    window.app.uiManager.updateProgress(data.progress);
    
    if (data.status === 'completed') {
      this.stopPolling();
      window.app.uiManager.showResult(data.result_url);
      window.app.uiManager.setFormLoading(false);
    } else if (data.status === 'failed') {
      this.stopPolling();
      window.app.uiManager.showError(`处理失败: ${data.error || '未知错误'}`);
      window.app.uiManager.setFormLoading(false);
    }
  }

  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }
}

/**
 * Main Application Class
 */
class App {
  constructor() {
    this.configManager = new ConfigManager();
    this.uiManager = new UIManager();
    this.voicePairManager = new VoicePairManager();
    this.dubbingService = new DubbingService();
  }

  async initialize() {
    try {
      // Load options first
      this.uiManager.showLoadingState();
      const options = await this.configManager.loadOptions();
      
      this.uiManager.populateSelect(
        this.uiManager.elements.engineSelect, 
        options.tts_engines || [], 
        'TTS 引擎', 
        DEFAULT_VALUES.TTS_ENGINE
      );
      this.uiManager.populateSelect(
        this.uiManager.elements.strategySelect, 
        options.strategies || [], 
        '策略', 
        DEFAULT_VALUES.STRATEGY
      );
      this.uiManager.populateSelect(
        this.uiManager.elements.languageSelect, 
        options.languages || [], 
        '语言',
        DEFAULT_VALUES.LANGUAGE
      );
      
      this.uiManager.hideLoadingState();

      // Load and apply configuration
      const basicConfig = await this.configManager.loadConfig();
      if (basicConfig) {
        this.applyBasicConfig(basicConfig);
        this.populateConfigTabs(basicConfig);
        this.voicePairManager.populateFromConfig(basicConfig.basic);
      }

    } catch (error) {
      console.error('Failed to initialize app:', error);
      this.uiManager.showError(error.message || '应用初始化失败');
      this.uiManager.hideLoadingState();
    }
  }

  applyBasicConfig(config) {
    if (config.basic) {
      if (config.basic.tts_engine) {
        this.uiManager.elements.engineSelect.value = config.basic.tts_engine;
      }
      if (config.basic.strategy) {
        this.uiManager.elements.strategySelect.value = config.basic.strategy;
      }
      if (config.basic.language) {
        this.uiManager.elements.languageSelect.value = config.basic.language;
      }
    }
  }

  populateConfigTabs(data) {
    this.populateConcurrencyTab(data.concurrency);
    this.populateSubtitleTab(data.subtitle_optimization);
    this.populateTimeTab(data.time_borrowing);
  }

  populateConcurrencyTab(config) {
    const tab = document.getElementById('tab-concurrency');
    tab.innerHTML = `
      <div class="options-row">
        <div class="form-group">
          <label class="form-label"><i class="fas fa-bolt"></i> TTS最大并发数</label>
          <input type="number" name="tts_max_concurrency" class="form-select" value="${config.tts_max_concurrency}">
        </div>
        <div class="form-group">
          <label class="form-label"><i class="fas fa-redo"></i> TTS最大重试次数</label>
          <input type="number" name="tts_max_retries" class="form-select" value="${config.tts_max_retries}">
        </div>
      </div>
    `;
  }

  populateSubtitleTab(config) {
    const tab = document.getElementById('tab-subtitle');
    tab.innerHTML = `
      <div class="options-row">
        <div class="form-group">
          <label class="form-label">LLM API Key</label>
          <div class="password-input-container">
            <input type="password" name="llm_api_key" class="form-select" value="${config.llm_api_key}">
            <i class="fas fa-eye toggle-password"></i>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">LLM Model</label>
          <input type="text" name="llm_model" class="form-select" value="${config.llm_model}">
        </div>
        <div class="form-group">
          <label class="form-label">Base URL</label>
          <input type="text" name="base_url" class="form-select" value="${config.base_url}">
        </div>
        <div class="form-group">
          <label class="form-label">中文最小字符时间 (ms)</label>
          <input type="number" name="chinese_char_min_time" class="form-select" value="${config.chinese_char_min_time}">
        </div>
        <div class="form-group">
          <label class="form-label">英文最小单词时间 (ms)</label>
          <input type="number" name="english_word_min_time" class="form-select" value="${config.english_word_min_time}">
        </div>
        <div class="form-group">
          <label class="form-label">LLM最大并发数</label>
          <input type="number" name="llm_max_concurrency" class="form-select" value="${config.llm_max_concurrency}">
        </div>
        <div class="form-group">
          <label class="form-label">LLM最大重试次数</label>
          <input type="number" name="llm_max_retries" class="form-select" value="${config.llm_max_retries}">
        </div>
        <div class="form-group">
          <label class="form-label">LLM超时 (s)</label>
          <input type="number" name="llm_timeout" class="form-select" value="${config.llm_timeout}">
        </div>
        <div class="form-group">
          <label class="form-label">优化后SRT输出目录</label>
          <input type="text" name="optimized_srt_output_file" class="form-select" value="${config.optimized_srt_output_file}">
        </div>
      </div>
    `;
  }

  populateTimeTab(config) {
    const tab = document.getElementById('tab-time');
    tab.innerHTML = `
      <div class="options-row">
        <div class="form-group">
          <label class="form-label">最小保护空隙 (ms)</label>
          <input type="number" name="min_gap_threshold" class="form-select" value="${config.min_gap_threshold}">
        </div>
        <div class="form-group">
          <label class="form-label">借用比例</label>
          <input type="number" step="0.1" name="borrow_ratio" class="form-select" value="${config.borrow_ratio}">
        </div>
        <div class="form-group">
          <label class="form-label">额外缓冲时间 (ms)</label>
          <input type="number" name="extra_buffer" class="form-select" value="${config.extra_buffer}">
        </div>
      </div>
    `;
  }

  async saveConfigFromForm() {
    const configData = {
      concurrency: {
        tts_max_concurrency: document.querySelector('[name="tts_max_concurrency"]')?.value || '',
        tts_max_retries: document.querySelector('[name="tts_max_retries"]')?.value || '',
      },
      subtitle_optimization: {
        llm_api_key: document.querySelector('[name="llm_api_key"]')?.value || '',
        llm_model: document.querySelector('[name="llm_model"]')?.value || '',
        base_url: document.querySelector('[name="base_url"]')?.value || '',
        chinese_char_min_time: document.querySelector('[name="chinese_char_min_time"]')?.value || '',
        english_word_min_time: document.querySelector('[name="english_word_min_time"]')?.value || '',
        llm_max_concurrency: document.querySelector('[name="llm_max_concurrency"]')?.value || '',
        llm_max_retries: document.querySelector('[name="llm_max_retries"]')?.value || '',
        llm_timeout: document.querySelector('[name="llm_timeout"]')?.value || '',
        optimized_srt_output_file: document.querySelector('[name="optimized_srt_output_file"]')?.value || '',
      },
      time_borrowing: {
        min_gap_threshold: document.querySelector('[name="min_gap_threshold"]')?.value || '',
        borrow_ratio: document.querySelector('[name="borrow_ratio"]')?.value || '',
        extra_buffer: document.querySelector('[name="extra_buffer"]')?.value || '',
      }
    };
    
    try {
      await this.configManager.saveConfig(configData);
      alert('配置已保存！');
    } catch (error) {
      alert('配置保存失败！');
    }
  }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.app = new App();
  window.app.initialize();

  // Add interactive effects
  const formElements = document.querySelectorAll('.form-textarea, .form-select');
  formElements.forEach(element => {
    element.addEventListener('focus', () => {
      if (element.parentElement) {
        element.parentElement.style.transform = 'scale(1.02)';
      }
    });
    
    element.addEventListener('blur', () => {
      if (element.parentElement) {
        element.parentElement.style.transform = 'scale(1)';
      }
    });
  });
});

// Add CSS for animations and error states
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
  
  .success-animation {
    animation: successPulse 0.6s ease-in-out;
  }
  
  @keyframes successPulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }
`;
document.head.appendChild(style);
