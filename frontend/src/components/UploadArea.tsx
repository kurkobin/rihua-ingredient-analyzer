import { useRef } from 'react'

interface UploadAreaProps {
  image: string | null
  onFile: (file: File) => void
}

export default function UploadArea({ image, onFile }: UploadAreaProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onFile(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      className={`upload-area ${image ? 'has-image' : ''}`}
      onClick={() => fileInputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      {image ? (
        <img src={image} alt="配料表预览" />
      ) : (
        <>
          <div className="upload-icon">📷</div>
          <div className="upload-tip">点击或拖拽上传配料表图片</div>
        </>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />
    </div>
  )
}
