# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ps.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),  # 包含整个 src 目录及其所有文件
    ],
    hiddenimports=[
        # src 模块
        'src',
        'src.api_server',
        'src.psd-img-replace-smartobject',  # 注意：文件名包含连字符
        'src.photoshop_service',
        'src.psd_parser',
        # src.services 模块
        'src.services',
        'src.services.photoshop_status_service',
        'src.services.psd_analysis_service',
        # src.utils 模块
        'src.utils',
        'src.utils.file_utils',
        'src.utils.image_utils',
        'src.utils.photoshop_diagnostics',
        'src.utils.photoshop_process',
        # FastAPI 相关
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # pydantic 相关
        'pydantic._internal',
        'pydantic._internal._generate_schema',
        # 其他可能需要的（如果安装了的话）
        'comtypes',
        'comtypes.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ps',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
