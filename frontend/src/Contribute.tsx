import { useState, useRef } from 'react'
import { API_BASE } from './constants'

interface Props {
  onBack: () => void
}

// 图片压缩(长边不超过 1600px,质量 0.8,避免大文件 OCR 超时)
async function compressImage(file: File): Promise<Blob> {
  const MAX_WIDTH = 1600
  const MAX_HEIGHT = 1600
  const QUALITY = 0.8

  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > MAX_WIDTH || height > MAX_HEIGHT) {
          const ratio = Math.min(MAX_WIDTH / width, MAX_HEIGHT / height)
          width = Math.round(width * ratio)
          height = Math.round(height * ratio)
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('无法创建 canvas 上下文'))
          return
        }
        ctx.drawImage(img, 0, 0, width, height)
        canvas.toBlob(
          (blob) => {
            if (blob) resolve(blob)
            else reject(new Error('图片压缩失败'))
          },
          'image/jpeg',
          QUALITY
        )
      }
      img.onerror = () => reject(new Error('图片加载失败'))
      img.src = e.target?.result as string
    }
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

function Contribute({ onBack }: Props) {
  const [image, setImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState<{ message: string; count: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 选择图片后自动提交(用户只需选图,无需额外操作)
  const handleFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('请上传图片文件')
      return
    }

    // 预览图片
    const reader = new FileReader()
    reader.onload = (e) => setImage(e.target?.result as string)
    reader.readAsDataURL(file)

    // 自动提交(减少操作步骤)
    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      let blob: Blob
      try {
        blob = await compressImage(file)
      } catch {
        blob = file
      }

      const formData = new FormData()
      formData.append('image', blob, 'contribute.jpg')

      const resp = await fetch(`${API_BASE}/api/contribute`, {
        method: 'POST',
        body: formData,
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || `请求失败(${resp.status})`)
      }
      const data = await resp.json()
      setSuccess({ message: data.message, count: data.count })
    } catch (e) {
      const msg = e instanceof Error ? e.message : '未知错误'
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        setError('网络连接失败,请检查网络或稍后重试')
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  // 重置,再贡献一张
  const handleReset = () => {
    setImage(null)
    setSuccess(null)
    setError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>贡献成分</h1>
        <p>帮助我们扩充成分数据库</p>
      </header>

      {/* 返回按钮 */}
      <div className="topbar">
        <button className="link-btn" onClick={onBack}>
          ← 返回首页
        </button>
      </div>

      {/* 说明卡片 */}
      {!success && !loading && (
        <div className="contribute-intro">
          <div className="contribute-intro-icon">🌱</div>
          <h3>为什么需要您的贡献?</h3>
          <p>
            我们的成分库还在成长中,可能缺少某些产品的成分信息。
            只需上传一张配料表图片,系统会自动识别并提取成分信息,
            经过审核后补充到数据库,让更多用户受益。
          </p>
          <p className="contribute-intro-tip">
            📌 只需上传图片,无需填写任何信息
          </p>
        </div>
      )}

      {/* 上传区(成功后隐藏) */}
      {!success && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFile(file)
            }}
          />
          <div
            className={`upload-area ${image ? 'has-image' : ''} ${dragging ? 'dragging' : ''}`}
            onClick={() => !loading && fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              const file = e.dataTransfer.files?.[0]
              if (file) handleFile(file)
            }}
          >
            {image ? (
              <img src={image} alt="预览" />
            ) : (
              <>
                <div className="upload-icon">📷</div>
                <div className="upload-tip">
                  点击上传或拖拽配料表图片到此处
                  <br />
                  <span style={{ fontSize: 12, color: '#b2bec3' }}>
                    选择图片后自动识别,无需其他操作
                  </span>
                </div>
              </>
            )}
          </div>
        </>
      )}

      {/* 加载状态 */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <div className="loading-steps">
            <div>正在压缩图片...</div>
            <div>正在 OCR 识别文字...</div>
            <div>正在提取成分信息...</div>
          </div>
          <div className="loading-tip">自动识别中,约需 10-30 秒,请耐心等待</div>
        </div>
      )}

      {/* 感谢提示(成功) */}
      {success && !loading && (
        <div className="contribute-success">
          <div className="contribute-success-icon">🎉</div>
          <h3>感谢您的贡献!</h3>
          <p className="contribute-success-msg">{success.message}</p>
          <p className="contribute-success-count">
            本次共识别并提交 <strong>{success.count}</strong> 个成分
          </p>
          <p className="contribute-success-thanks">
            您的分享将帮助更多用户了解产品成分,感谢您对社区的支持! 💚
          </p>
          <div className="contribute-success-actions">
            <button className="btn btn-secondary" onClick={handleReset}>
              再贡献一张
            </button>
            <button className="btn btn-primary" onClick={onBack}>
              返回首页
            </button>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && !loading && (
        <div className="error">⚠️ {error}</div>
      )}
    </div>
  )
}

export default Contribute
