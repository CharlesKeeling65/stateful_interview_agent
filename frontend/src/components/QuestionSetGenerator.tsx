import { useState, useEffect, useCallback } from 'react'
import {
  createQuestionSet,
  getQuestionSet,
  listQuestionSets,
  reviseQuestion,
  validateQuestionSet,
  getQuestionSetCoverage,
  deleteQuestionSet,
  getQuestionVersions,
  getQuestionVersionDiff,
  rollbackQuestionVersion,
  cascadeReviseQuestion,
  type QuestionSetResponse,
  type GeneratedQuestionResponse,
  type QuestionRevisionResponse,
  type ValidationReport,
  type CoverageReport,
  type QuestionVersionResponse,
  type QuestionVersionDiff,
  type CascadeRevisionResponse,
} from '../api/client'

interface QuestionSetGeneratorProps {
  locale: 'en' | 'zh'
}

export function QuestionSetGenerator({ locale }: QuestionSetGeneratorProps) {
  const [repositorySource, setRepositorySource] = useState<'remote' | 'local'>('remote')
  const [repositoryUrl, setRepositoryUrl] = useState('')
  const [totalQuestions, setTotalQuestions] = useState(40)
  const [codeDetailRatio, setCodeDetailRatio] = useState(0.85)
  const [minCoreFileCoverage, setMinCoreFileCoverage] = useState(0.90)
  
  const [questionSets, setQuestionSets] = useState<QuestionSetResponse[]>([])
  const [selectedQuestionSet, setSelectedQuestionSet] = useState<QuestionSetResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Revision state
  const [selectedQuestion, setSelectedQuestion] = useState<GeneratedQuestionResponse | null>(null)
  const [chineseInstruction, setChineseInstruction] = useState('')
  const [revisionResult, setRevisionResult] = useState<QuestionRevisionResponse | null>(null)
  const [revising, setRevising] = useState(false)
  
  // Validation and coverage state
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null)
  const [coverageReport, setCoverageReport] = useState<CoverageReport | null>(null)
  
  // Polling state
  const [, setPolling] = useState(false)
  
  // Version management state
  const [versions, setVersions] = useState<QuestionVersionResponse[]>([])
  const [selectedVersion, setSelectedVersion] = useState<QuestionVersionResponse | null>(null)
  const [versionDiff, setVersionDiff] = useState<QuestionVersionDiff | null>(null)
  const [showVersionPanel, setShowVersionPanel] = useState(false)
  const [cascadeResult, setCascadeResult] = useState<CascadeRevisionResponse | null>(null)
  const [cascading, setCascading] = useState(false)
  
  // Copy state
  const [copiedQuestionId, setCopiedQuestionId] = useState<number | null>(null)
  
  const t = useCallback((key: string) => {
    const translations: Record<string, Record<string, string>> = {
      en: {
        'questionSet.title': 'Question Set Generator',
        'questionSet.description': 'Generate a complete question set for repository code understanding',
        'questionSet.repositorySource': 'Repository Source',
        'questionSet.repositorySource.remote': 'Remote Repository',
        'questionSet.repositorySource.local': 'Local Path',
        'questionSet.repositoryUrl': 'Repository URL',
        'questionSet.repositoryUrl.placeholder': 'https://github.com/username/repository',
        'questionSet.repositoryLocal.placeholder': '/path/to/local/repository',
        'questionSet.totalQuestions': 'Total Questions',
        'questionSet.codeDetailRatio': 'Code Detail Ratio',
        'questionSet.minCoreFileCoverage': 'Min Core File Coverage',
        'questionSet.generate': 'Generate Question Set',
        'questionSet.generating': 'Generating...',
        'questionSet.list': 'Question Sets',
        'questionSet.select': 'Select',
        'questionSet.delete': 'Delete',
        'questionSet.questions': 'Questions',
        'questionSet.phase': 'Phase',
        'questionSet.question': 'Question',
        'questionSet.targetFiles': 'Target Files',
        'questionSet.qualityScore': 'Quality Score',
        'questionSet.revise': 'Revise',
        'questionSet.revision.title': 'Revise Question',
        'questionSet.revision.instruction': 'Chinese Instruction',
        'questionSet.revision.instruction.placeholder': '例如：这个问题太泛了，改成具体问 main.py 里的 run_agent 方法',
        'questionSet.revision.submit': 'Revise',
        'questionSet.revision.result': 'Revision Result',
        'questionSet.revision.original': 'Original',
        'questionSet.revision.revised': 'Revised',
        'questionSet.revision.warnings': 'Warnings',
        'questionSet.validation': 'Validation Report',
        'questionSet.validation.isValid': 'Is Valid',
        'questionSet.validation.totalQuestions': 'Total Questions',
        'questionSet.validation.codeDetailCount': 'Code Detail Count',
        'questionSet.validation.codeDetailRatio': 'Code Detail Ratio',
        'questionSet.validation.coreFilesDetected': 'Core Files Detected',
        'questionSet.validation.coreFilesCovered': 'Core Files Covered',
        'questionSet.validation.coreFileCoverage': 'Core File Coverage',
        'questionSet.validation.warnings': 'Warnings',
        'questionSet.validation.errors': 'Errors',
        'questionSet.coverage': 'Coverage Report',
        'questionSet.coverage.totalCoreFiles': 'Total Core Files',
        'questionSet.coverage.coveredCoreFiles': 'Covered Core Files',
        'questionSet.coverage.coveragePercentage': 'Coverage Percentage',
        'questionSet.coverage.uncoveredFiles': 'Uncovered Files',
        'questionSet.status.pending': 'Pending',
        'questionSet.status.analyzing': 'Analyzing',
        'questionSet.status.generating': 'Generating',
        'questionSet.status.validating': 'Validating',
        'questionSet.status.completed': 'Completed',
        'questionSet.status.failed': 'Failed',
        'questionSet.error': 'Error',
        'questionSet.noQuestionSets': 'No question sets yet',
        'questionSet.selectQuestionSet': 'Select a question set to view details',
        'questionSet.version.history': 'Version History',
        'questionSet.version.diff': 'View Diff',
        'questionSet.version.rollback': 'Rollback',
        'questionSet.version.current': 'Current',
        'questionSet.version.created': 'Created',
        'questionSet.version.revised': 'Revised',
        'questionSet.version.rollbacked': 'Rolled Back',
        'questionSet.version.cascade': 'Cascade Regenerated',
        'questionSet.copy': 'Copy',
        'questionSet.copied': 'Copied!',
        'questionSet.cascade.revise': 'Cascade Revise',
        'questionSet.cascade.result': 'Cascade Result',
      },
      zh: {
        'questionSet.title': '问题集生成器',
        'questionSet.description': '为代码仓库生成完整的问题集，用于代码理解',
        'questionSet.repositorySource': '仓库来源',
        'questionSet.repositorySource.remote': '远程仓库',
        'questionSet.repositorySource.local': '本地路径',
        'questionSet.repositoryUrl': '仓库 URL',
        'questionSet.repositoryUrl.placeholder': 'https://github.com/用户名/仓库名',
        'questionSet.repositoryLocal.placeholder': '/path/to/local/repository',
        'questionSet.totalQuestions': '问题总数',
        'questionSet.codeDetailRatio': '代码细节比例',
        'questionSet.minCoreFileCoverage': '最小核心文件覆盖率',
        'questionSet.generate': '生成问题集',
        'questionSet.generating': '生成中...',
        'questionSet.list': '问题集列表',
        'questionSet.select': '选择',
        'questionSet.delete': '删除',
        'questionSet.questions': '问题',
        'questionSet.phase': '阶段',
        'questionSet.question': '问题',
        'questionSet.targetFiles': '目标文件',
        'questionSet.qualityScore': '质量分数',
        'questionSet.revise': '修订',
        'questionSet.revision.title': '修订问题',
        'questionSet.revision.instruction': '中文指令',
        'questionSet.revision.instruction.placeholder': '例如：这个问题太泛了，改成具体问 main.py 里的 run_agent 方法',
        'questionSet.revision.submit': '修订',
        'questionSet.revision.result': '修订结果',
        'questionSet.revision.original': '原始问题',
        'questionSet.revision.revised': '修订后',
        'questionSet.revision.warnings': '警告',
        'questionSet.validation': '验证报告',
        'questionSet.validation.isValid': '是否有效',
        'questionSet.validation.totalQuestions': '问题总数',
        'questionSet.validation.codeDetailCount': '代码细节问题数',
        'questionSet.validation.codeDetailRatio': '代码细节比例',
        'questionSet.validation.coreFilesDetected': '检测到的核心文件',
        'questionSet.validation.coreFilesCovered': '已覆盖的核心文件',
        'questionSet.validation.coreFileCoverage': '核心文件覆盖率',
        'questionSet.validation.warnings': '警告',
        'questionSet.validation.errors': '错误',
        'questionSet.coverage': '覆盖率报告',
        'questionSet.coverage.totalCoreFiles': '核心文件总数',
        'questionSet.coverage.coveredCoreFiles': '已覆盖的核心文件',
        'questionSet.coverage.coveragePercentage': '覆盖率百分比',
        'questionSet.coverage.uncoveredFiles': '未覆盖的文件',
        'questionSet.status.pending': '待处理',
        'questionSet.status.analyzing': '分析中',
        'questionSet.status.generating': '生成中',
        'questionSet.status.validating': '验证中',
        'questionSet.status.completed': '已完成',
        'questionSet.status.failed': '失败',
        'questionSet.error': '错误',
        'questionSet.noQuestionSets': '暂无问题集',
        'questionSet.selectQuestionSet': '选择一个问题集查看详情',
        'questionSet.version.history': '版本历史',
        'questionSet.version.diff': '查看差异',
        'questionSet.version.rollback': '回滚',
        'questionSet.version.current': '当前版本',
        'questionSet.version.created': '创建时间',
        'questionSet.version.revised': '修订时间',
        'questionSet.version.rollbacked': '回滚时间',
        'questionSet.version.cascade': '级联重新生成',
        'questionSet.copy': '复制',
        'questionSet.copied': '已复制！',
        'questionSet.cascade.revise': '级联修订',
        'questionSet.cascade.result': '级联结果',
      },
    }
    return translations[locale]?.[key] || key
  }, [locale])
  
  // Load question sets on mount
  useEffect(() => {
    loadQuestionSets()
  }, [])
  
  // Poll for status updates
  useEffect(() => {
    if (!selectedQuestionSet || selectedQuestionSet.status === 'completed' || selectedQuestionSet.status === 'failed') {
      setPolling(false)
      return
    }
    
    setPolling(true)
    const interval = setInterval(async () => {
      try {
        const updated = await getQuestionSet(selectedQuestionSet.id)
        setSelectedQuestionSet(updated)
        
        if (updated.status === 'completed' || updated.status === 'failed') {
          setPolling(false)
          clearInterval(interval)
          
          // Reload validation and coverage
          if (updated.status === 'completed') {
            const [validation, coverage] = await Promise.all([
              validateQuestionSet(updated.id),
              getQuestionSetCoverage(updated.id),
            ])
            setValidationReport(validation)
            setCoverageReport(coverage)
          }
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 2000)
    
    return () => {
      clearInterval(interval)
      setPolling(false)
    }
  }, [selectedQuestionSet])
  
  const loadQuestionSets = async () => {
    try {
      const response = await listQuestionSets()
      setQuestionSets(response.question_sets)
    } catch (err) {
      console.error('Failed to load question sets:', err)
    }
  }
  
  const handleGenerate = async () => {
    if (!repositoryUrl) {
      setError(repositorySource === 'remote' 
        ? 'Please enter a repository URL' 
        : 'Please enter a local path'
      )
      return
    }
    
    // Validate input format
    if (repositorySource === 'remote' && !repositoryUrl.startsWith('http')) {
      setError('Remote repository URL must start with http:// or https://')
      return
    }
    
    if (repositorySource === 'local' && !repositoryUrl.startsWith('/')) {
      setError('Local path must be an absolute path starting with /')
      return
    }
    
    setLoading(true)
    setError(null)
    
    try {
      const questionSet = await createQuestionSet({
        repository_url: repositoryUrl,
        repository_source: repositorySource,
        total_questions: totalQuestions,
        code_detail_ratio: codeDetailRatio,
        min_core_file_coverage: minCoreFileCoverage,
      })
      
      setSelectedQuestionSet(questionSet)
      setQuestionSets(prev => [questionSet, ...prev])
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate question set')
    } finally {
      setLoading(false)
    }
  }
  
  const handleSelectQuestionSet = async (questionSet: QuestionSetResponse) => {
    setSelectedQuestionSet(questionSet)
    setSelectedQuestion(null)
    setRevisionResult(null)
    setChineseInstruction('')
    
    // Load validation and coverage if completed
    if (questionSet.status === 'completed') {
      try {
        const [validation, coverage] = await Promise.all([
          validateQuestionSet(questionSet.id),
          getQuestionSetCoverage(questionSet.id),
        ])
        setValidationReport(validation)
        setCoverageReport(coverage)
      } catch (err) {
        console.error('Failed to load reports:', err)
      }
    }
  }
  
  const handleDeleteQuestionSet = async (questionSetId: number) => {
    if (!confirm('Are you sure you want to delete this question set?')) {
      return
    }
    
    try {
      await deleteQuestionSet(questionSetId)
      setQuestionSets(prev => prev.filter(qs => qs.id !== questionSetId))
      
      if (selectedQuestionSet?.id === questionSetId) {
        setSelectedQuestionSet(null)
        setValidationReport(null)
        setCoverageReport(null)
      }
    } catch (err) {
      console.error('Failed to delete question set:', err)
    }
  }
  
  const handleReviseQuestion = async () => {
    if (!selectedQuestionSet || !selectedQuestion || !chineseInstruction) {
      return
    }
    
    setRevising(true)
    
    try {
      const result = await reviseQuestion(selectedQuestionSet.id, {
        question_id: selectedQuestion.id,
        chinese_instruction: chineseInstruction,
      })
      
      setRevisionResult(result)
      
      // Update question in the list
      if (selectedQuestionSet) {
        const updatedQuestions = selectedQuestionSet.questions.map(q => 
          q.id === selectedQuestion.id 
            ? { ...q, question_text: result.revised_question }
            : q
        )
        setSelectedQuestionSet({
          ...selectedQuestionSet,
          questions: updatedQuestions,
        })
      }
      
    } catch (err) {
      console.error('Failed to revise question:', err)
    } finally {
      setRevising(false)
    }
  }
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600'
      case 'failed': return 'text-red-600'
      case 'analyzing':
      case 'generating':
      case 'validating': return 'text-yellow-600'
      default: return 'text-gray-600'
    }
  }
  
  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case 'Panorama Mapping': return 'bg-blue-100 text-blue-800'
      case 'Architecture Understanding': return 'bg-purple-100 text-purple-800'
      case 'Code Detail Completion': return 'bg-green-100 text-green-800'
      case 'Use Cases & Scenarios': return 'bg-orange-100 text-orange-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }
  
  const copyToClipboard = async (text: string, questionId: number) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedQuestionId(questionId)
      setTimeout(() => setCopiedQuestionId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }
  
  const loadVersions = async (questionId: number) => {
    if (!selectedQuestionSet) return
    
    try {
      const versionsList = await getQuestionVersions(selectedQuestionSet.id, questionId)
      setVersions(versionsList)
      setShowVersionPanel(true)
    } catch (err) {
      console.error('Failed to load versions:', err)
    }
  }
  
  const loadVersionDiff = async (questionId: number, v1: number, v2: number) => {
    if (!selectedQuestionSet) return
    
    try {
      const diff = await getQuestionVersionDiff(selectedQuestionSet.id, questionId, v1, v2)
      setVersionDiff(diff)
    } catch (err) {
      console.error('Failed to load version diff:', err)
    }
  }
  
  const handleRollback = async (questionId: number, versionNo: number) => {
    if (!selectedQuestionSet) return
    
    try {
      await rollbackQuestionVersion(selectedQuestionSet.id, questionId, {
        version_no: versionNo,
        reason: 'User requested rollback',
      })
      
      // Reload question set to get updated question
      const updatedQuestionSet = await getQuestionSet(selectedQuestionSet.id)
      setSelectedQuestionSet(updatedQuestionSet)
      
      // Update selected question if it was the one rolled back
      if (selectedQuestion?.id === questionId) {
        const updatedQuestion = updatedQuestionSet.questions.find(q => q.id === questionId)
        if (updatedQuestion) {
          setSelectedQuestion(updatedQuestion)
        }
      }
      
      // Reload versions
      await loadVersions(questionId)
    } catch (err) {
      console.error('Failed to rollback:', err)
    }
  }
  
  const handleCascadeRevise = async () => {
    if (!selectedQuestionSet || !selectedQuestion || !chineseInstruction) {
      return
    }
    
    setCascading(true)
    
    try {
      const result = await cascadeReviseQuestion(selectedQuestionSet.id, selectedQuestion.id, {
        question_id: selectedQuestion.id,
        chinese_instruction: chineseInstruction,
        cascade: true,
      })
      
      setCascadeResult(result)
      
      // Reload question set to get updated questions
      const updatedQuestionSet = await getQuestionSet(selectedQuestionSet.id)
      setSelectedQuestionSet(updatedQuestionSet)
      
      // Update selected question
      const updatedQuestion = updatedQuestionSet.questions.find(q => q.id === selectedQuestion.id)
      if (updatedQuestion) {
        setSelectedQuestion(updatedQuestion)
      }
      
    } catch (err) {
      console.error('Failed to cascade revise:', err)
    } finally {
      setCascading(false)
    }
  }
  
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">{t('questionSet.title')}</h1>
      <p className="text-gray-600 mb-6">{t('questionSet.description')}</p>
      
      {/* Generation Form */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">{t('questionSet.generate')}</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.repositorySource')}
            </label>
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => setRepositorySource('remote')}
                className={`px-3 py-1 text-sm rounded-md ${
                  repositorySource === 'remote'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {t('questionSet.repositorySource.remote')}
              </button>
              <button
                type="button"
                onClick={() => setRepositorySource('local')}
                className={`px-3 py-1 text-sm rounded-md ${
                  repositorySource === 'local'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {t('questionSet.repositorySource.local')}
              </button>
            </div>
            <input
              type="text"
              value={repositoryUrl}
              onChange={(e) => setRepositoryUrl(e.target.value)}
              placeholder={repositorySource === 'remote' 
                ? t('questionSet.repositoryUrl.placeholder')
                : t('questionSet.repositoryLocal.placeholder')
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.totalQuestions')}
            </label>
            <input
              type="number"
              value={totalQuestions}
              onChange={(e) => setTotalQuestions(parseInt(e.target.value) || 40)}
              min={35}
              max={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.codeDetailRatio')}
            </label>
            <input
              type="number"
              value={codeDetailRatio}
              onChange={(e) => setCodeDetailRatio(parseFloat(e.target.value) || 0.85)}
              min={0.5}
              max={1.0}
              step={0.01}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('questionSet.minCoreFileCoverage')}
            </label>
            <input
              type="number"
              value={minCoreFileCoverage}
              onChange={(e) => setMinCoreFileCoverage(parseFloat(e.target.value) || 0.90)}
              min={0.5}
              max={1.0}
              step={0.01}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}
        
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? t('questionSet.generating') : t('questionSet.generate')}
        </button>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Question Sets List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">{t('questionSet.list')}</h2>
          
          {questionSets.length === 0 ? (
            <p className="text-gray-500">{t('questionSet.noQuestionSets')}</p>
          ) : (
            <div className="space-y-3">
              {questionSets.map(qs => (
                <div
                  key={qs.id}
                  className={`p-3 border rounded cursor-pointer ${
                    selectedQuestionSet?.id === qs.id 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => handleSelectQuestionSet(qs)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium text-sm truncate max-w-[200px]">
                        {qs.repository_url}
                      </div>
                      <div className={`text-xs ${getStatusColor(qs.status)}`}>
                        {t(`questionSet.status.${qs.status}`)}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteQuestionSet(qs.id)
                      }}
                      className="text-red-500 hover:text-red-700 text-xs"
                    >
                      {t('questionSet.delete')}
                    </button>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {qs.question_count} {t('questionSet.questions')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Questions List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">
            {selectedQuestionSet 
              ? `${t('questionSet.questions')} (${selectedQuestionSet.question_count})`
              : t('questionSet.selectQuestionSet')
            }
          </h2>
          
          {selectedQuestionSet && (
            <div className="space-y-4 max-h-[800px] overflow-y-auto pr-2">
              {selectedQuestionSet.questions.map(q => (
                <div
                  key={q.id}
                  className={`p-4 border rounded-lg ${
                    selectedQuestion?.id === q.id 
                      ? 'border-green-500 bg-green-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {/* Question header */}
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded ${getPhaseColor(q.phase)}`}>
                        {q.phase}
                      </span>
                      <span className="text-xs text-gray-500 font-medium">
                        Q{q.question_no}
                      </span>
                      <span className="text-xs text-gray-400">
                        v{q.current_version_no}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          copyToClipboard(q.question_text, q.id)
                        }}
                        className={`text-xs px-2 py-1 rounded ${
                          copiedQuestionId === q.id 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        {copiedQuestionId === q.id ? t('questionSet.copied') : t('questionSet.copy')}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          loadVersions(q.id)
                        }}
                        className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-600 hover:bg-blue-200"
                      >
                        {t('questionSet.version.history')}
                      </button>
                    </div>
                  </div>
                  
                  {/* Question text */}
                  <div 
                    className="text-sm text-gray-800 mb-2 cursor-pointer"
                    onClick={() => setSelectedQuestion(q)}
                  >
                    {q.question_text}
                  </div>
                  
                  {/* Target files */}
                  {q.target_files.length > 0 && (
                    <div className="text-xs text-gray-500">
                      {t('questionSet.targetFiles')}: {q.target_files.slice(0, 2).join(', ')}
                      {q.target_files.length > 2 && ` +${q.target_files.length - 2}`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Question Details and Revision */}
        <div className="bg-white rounded-lg shadow p-6">
          {selectedQuestion ? (
            <>
              <h2 className="text-lg font-semibold mb-4">{t('questionSet.revision.title')}</h2>
              
              <div className="mb-4">
                <div className="text-sm text-gray-500 mb-1">{t('questionSet.question')}</div>
                <div className="p-3 bg-gray-50 rounded">
                  {selectedQuestion.question_text}
                </div>
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('questionSet.revision.instruction')}
                </label>
                <textarea
                  value={chineseInstruction}
                  onChange={(e) => setChineseInstruction(e.target.value)}
                  placeholder={t('questionSet.revision.instruction.placeholder')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
              
              <div className="flex gap-2 mb-4">
                <button
                  onClick={handleReviseQuestion}
                  disabled={revising || !chineseInstruction}
                  className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:opacity-50"
                >
                  {revising ? '...' : t('questionSet.revision.submit')}
                </button>
                
                <button
                  onClick={handleCascadeRevise}
                  disabled={cascading || !chineseInstruction}
                  className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:opacity-50"
                >
                  {cascading ? '...' : t('questionSet.cascade.revise')}
                </button>
              </div>
              
              {revisionResult && (
                <div className="border-t pt-4">
                  <h3 className="font-medium mb-2">{t('questionSet.revision.result')}</h3>
                  
                  <div className="mb-2">
                    <div className="text-xs text-gray-500">{t('questionSet.revision.original')}</div>
                    <div className="text-sm bg-red-50 p-2 rounded">
                      {revisionResult.original_question}
                    </div>
                  </div>
                  
                  <div className="mb-2">
                    <div className="text-xs text-gray-500">{t('questionSet.revision.revised')}</div>
                    <div className="text-sm bg-green-50 p-2 rounded">
                      {revisionResult.revised_question}
                    </div>
                  </div>
                  
                  {revisionResult.warnings.length > 0 && (
                    <div className="mb-2">
                      <div className="text-xs text-gray-500">{t('questionSet.revision.warnings')}</div>
                      <ul className="text-sm text-yellow-600 list-disc list-inside">
                        {revisionResult.warnings.map((warning, i) => (
                          <li key={i}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              
              {cascadeResult && (
                <div className="border-t pt-4 mt-4">
                  <h3 className="font-medium mb-2">{t('questionSet.cascade.result')}</h3>
                  
                  <div className="mb-2">
                    <div className="text-xs text-gray-500">{t('questionSet.revision.original')}</div>
                    <div className="text-sm bg-red-50 p-2 rounded">
                      {cascadeResult.original_question}
                    </div>
                  </div>
                  
                  <div className="mb-2">
                    <div className="text-xs text-gray-500">{t('questionSet.revision.revised')}</div>
                    <div className="text-sm bg-green-50 p-2 rounded">
                      {cascadeResult.revised_question}
                    </div>
                  </div>
                  
                  {cascadeResult.cascade_results.length > 0 && (
                    <div className="mb-2">
                      <div className="text-xs text-gray-500 mb-1">Cascade Effects:</div>
                      <ul className="text-sm list-disc list-inside">
                        {cascadeResult.cascade_results.map((result, i) => (
                          <li key={i} className={
                            result.status === 'regenerated' ? 'text-green-600' :
                            result.status === 'failed' ? 'text-red-600' : 'text-yellow-600'
                          }>
                            Q{result.question_no}: {result.status}
                            {result.error && ` - ${result.error}`}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="text-gray-500 text-center py-8">
              {t('questionSet.selectQuestionSet')}
            </div>
          )}
        </div>
      </div>
      
      {/* Validation and Coverage Reports */}
      {selectedQuestionSet?.status === 'completed' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          {/* Validation Report */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">{t('questionSet.validation')}</h2>
            
            {validationReport && (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.isValid')}</span>
                  <span className={`font-medium ${validationReport.is_valid ? 'text-green-600' : 'text-red-600'}`}>
                    {validationReport.is_valid ? '✓' : '✗'}
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.totalQuestions')}</span>
                  <span className="font-medium">{validationReport.total_questions}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.codeDetailCount')}</span>
                  <span className="font-medium">{validationReport.code_detail_count}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.codeDetailRatio')}</span>
                  <span className="font-medium">
                    {(validationReport.code_detail_ratio * 100).toFixed(1)}%
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.coreFilesDetected')}</span>
                  <span className="font-medium">{validationReport.core_files_detected}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.coreFilesCovered')}</span>
                  <span className="font-medium">{validationReport.core_files_covered}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.validation.coreFileCoverage')}</span>
                  <span className="font-medium">
                    {(validationReport.core_file_coverage * 100).toFixed(1)}%
                  </span>
                </div>
                
                {validationReport.warnings.length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-1">{t('questionSet.validation.warnings')}</div>
                    <ul className="text-sm text-yellow-600 list-disc list-inside">
                      {validationReport.warnings.map((warning, i) => (
                        <li key={i}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {validationReport.errors.length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-1">{t('questionSet.validation.errors')}</div>
                    <ul className="text-sm text-red-600 list-disc list-inside">
                      {validationReport.errors.map((error, i) => (
                        <li key={i}>{error}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Coverage Report */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">{t('questionSet.coverage')}</h2>
            
            {coverageReport && (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.coverage.totalCoreFiles')}</span>
                  <span className="font-medium">{coverageReport.total_core_files}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.coverage.coveredCoreFiles')}</span>
                  <span className="font-medium">{coverageReport.covered_core_files}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">{t('questionSet.coverage.coveragePercentage')}</span>
                  <span className="font-medium">
                    {(coverageReport.coverage_percentage * 100).toFixed(1)}%
                  </span>
                </div>
                
                {coverageReport.uncovered_files.length > 0 && (
                  <div>
                    <div className="text-sm text-gray-600 mb-1">{t('questionSet.coverage.uncoveredFiles')}</div>
                    <ul className="text-sm text-gray-500 list-disc list-inside max-h-40 overflow-y-auto">
                      {coverageReport.uncovered_files.map((file, i) => (
                        <li key={i}>{file}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Version History Panel */}
      {showVersionPanel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
            <div className="flex justify-between items-center p-4 border-b">
              <h2 className="text-lg font-semibold">{t('questionSet.version.history')}</h2>
              <button
                onClick={() => {
                  setShowVersionPanel(false)
                  setVersions([])
                  setVersionDiff(null)
                  setSelectedVersion(null)
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            
            <div className="flex h-[calc(90vh-120px)]">
              {/* Version list */}
              <div className="w-1/3 border-r overflow-y-auto p-4">
                <h3 className="font-medium mb-3">Versions</h3>
                <div className="space-y-2">
                  {versions.map((version, index) => (
                    <div
                      key={version.id}
                      className={`p-3 border rounded cursor-pointer ${
                        selectedVersion?.id === version.id 
                          ? 'border-blue-500 bg-blue-50' 
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => setSelectedVersion(version)}
                    >
                      <div className="flex justify-between items-start mb-1">
                        <span className="text-sm font-medium">v{version.version_no}</span>
                        <span className={`text-xs px-2 py-1 rounded ${
                          version.change_type === 'generated' ? 'bg-green-100 text-green-800' :
                          version.change_type === 'revised' ? 'bg-yellow-100 text-yellow-800' :
                          version.change_type === 'rollback' ? 'bg-purple-100 text-purple-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {version.change_type}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 mb-1">
                        {version.created_at ? new Date(version.created_at).toLocaleString() : ''}
                      </div>
                      <div className="text-xs text-gray-600 truncate">
                        {version.change_summary}
                      </div>
                      
                      {/* Action buttons */}
                      <div className="flex gap-1 mt-2">
                        {index > 0 && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              loadVersionDiff(versions[0].question_id, versions[index].version_no, versions[index-1].version_no)
                            }}
                            className="text-xs px-2 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200"
                          >
                            {t('questionSet.version.diff')}
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRollback(version.question_id, version.version_no)
                          }}
                          className="text-xs px-2 py-1 bg-red-100 text-red-600 rounded hover:bg-red-200"
                        >
                          {t('questionSet.version.rollback')}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Version detail */}
              <div className="w-2/3 overflow-y-auto p-4">
                {selectedVersion ? (
                  <div>
                    <h3 className="font-medium mb-3">
                      Version {selectedVersion.version_no} - {selectedVersion.change_type}
                    </h3>
                    
                    <div className="mb-4">
                      <div className="text-sm text-gray-500 mb-1">Question Text:</div>
                      <div className="p-3 bg-gray-50 rounded">
                        {selectedVersion.question_text}
                      </div>
                    </div>
                    
                    <div className="mb-4">
                      <div className="text-sm text-gray-500 mb-1">Change Summary:</div>
                      <div className="p-3 bg-gray-50 rounded">
                        {selectedVersion.change_summary || 'No summary'}
                      </div>
                    </div>
                    
                    <div className="mb-4">
                      <div className="text-sm text-gray-500 mb-1">Created At:</div>
                      <div className="p-3 bg-gray-50 rounded">
                        {selectedVersion.created_at ? new Date(selectedVersion.created_at).toLocaleString() : 'Unknown'}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-gray-500 text-center py-8">
                    Select a version to view details
                  </div>
                )}
                
                {/* Diff view */}
                {versionDiff && (
                  <div className="mt-6">
                    <h3 className="font-medium mb-3">
                      Diff: v{versionDiff.version_from.version_no} → v{versionDiff.version_to.version_no}
                    </h3>
                    
                    <div 
                      className="border rounded overflow-auto max-h-96"
                      dangerouslySetInnerHTML={{ __html: versionDiff.diff_html }}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
