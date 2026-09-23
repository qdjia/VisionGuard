# Runtime Size Audit

Generated: `2026-09-23T13:40:11.245300+00:00`

Reference Runtime: `5,311,923,777` bytes (`4.947 GiB`), `7,933` files.

## Component breakdown

| Component | Bytes | MiB | Share |
|---|---:|---:|---:|
| CUDA/cuDNN libraries | 3,130,810,384 | 2,985.773 | 58.939% |
| PyTorch | 1,170,333,771 | 1,116.117 | 22.032% |
| Paddle | 322,655,988 | 307.709 | 6.074% |
| Others | 196,918,948 | 187.797 | 3.707% |
| Polars | 175,884,800 | 167.737 | 3.311% |
| OpenCV | 116,231,880 | 110.847 | 2.188% |
| SciPy | 75,559,936 | 72.060 | 1.422% |
| Transformers/Hugging Face | 63,352,589 | 60.418 | 1.193% |
| NumPy | 28,174,515 | 26.869 | 0.530% |
| Matplotlib | 14,340,082 | 13.676 | 0.270% |
| scikit-learn | 12,950,418 | 12.350 | 0.244% |
| Ultralytics | 4,022,935 | 3.837 | 0.076% |
| PaddleX | 687,531 | 0.656 | 0.013% |

## Top 50 largest files

| File | Bytes | MiB |
|---|---:|---:|
| `_internal/torch/lib/torch_cuda.dll` | 811,561,984 | 773.966 |
| `_internal/torch/lib/cublasLt64_12.dll` | 674,667,520 | 643.413 |
| `_internal/torch/lib/cudnn_engines_precompiled64_9.dll` | 481,015,408 | 458.732 |
| `_internal/torch/lib/cusparse64_12.dll` | 379,535,872 | 361.954 |
| `_internal/torch/lib/cufft64_11.dll` | 276,121,600 | 263.330 |
| `_internal/torch/lib/cudnn_adv64_9.dll` | 269,016,688 | 256.554 |
| `_internal/torch/lib/torch_cpu.dll` | 265,966,080 | 253.645 |
| `_internal/torch/lib/cusolver64_11.dll` | 225,683,456 | 215.229 |
| `_internal/_polars_runtime_32/_polars_runtime.pyd` | 175,884,800 | 167.737 |
| `_internal/torch/lib/cusolverMg64_11.dll` | 157,071,360 | 149.795 |
| `_internal/paddle/base/libpaddle.pyd` | 126,850,048 | 120.974 |
| `_internal/torch/lib/cublas64_12.dll` | 113,716,224 | 108.448 |
| `_internal/torch/lib/cudnn_ops64_9.dll` | 105,604,208 | 100.712 |
| `visionguard-runtime.exe` | 95,694,464 | 91.261 |
| `_internal/paddle/libs/mklml.dll` | 92,649,344 | 88.357 |
| `_internal/cv2/cv2.pyd` | 89,814,528 | 85.654 |
| `_internal/torch/lib/nvrtc64_120_0.alt.dll` | 86,794,240 | 82.773 |
| `_internal/torch/lib/nvrtc64_120_0.dll` | 86,728,192 | 82.710 |
| `_internal/torch/lib/nvJitLink_120_0.dll` | 77,860,352 | 74.253 |
| `_internal/torch/lib/curand64_10.dll` | 71,955,968 | 68.623 |
| `_internal/torch/lib/cudnn_heuristic64_9.dll` | 58,874,992 | 56.148 |
| `_internal/paddle/libs/mkldnn.dll` | 47,322,112 | 45.130 |
| `_internal/paddle/libs/phi.dll` | 42,797,056 | 40.814 |
| `_internal/torch/lib/cudnn_engines_runtime_compiled64_9.dll` | 27,759,216 | 26.473 |
| `_internal/cv2/opencv_videoio_ffmpeg4100_64.dll` | 26,391,552 | 25.169 |
| `_internal/torch/lib/nvperf_host.dll` | 21,641,792 | 20.639 |
| `_internal/numpy.libs/libscipy_openblas64_-9e3e5a4229c1ca39f10dc82bba9e2b2b.dll` | 20,403,712 | 19.458 |
| `_internal/scipy.libs/libscipy_openblas-64eda39e79589aedb16f58e5547eb599.dll` | 20,260,864 | 19.322 |
| `_internal/torch/lib/torch_python.dll` | 19,002,368 | 18.122 |
| `_internal/cryptography/hazmat/bindings/_rust.pyd` | 9,943,040 | 9.482 |
| `_internal/hf_xet/hf_xet.pyd` | 9,499,136 | 9.059 |
| `_internal/paddle/libs/liblapack.dll` | 7,895,054 | 7.529 |
| `_internal/PIL/_avif.cp311-win_amd64.pyd` | 7,888,896 | 7.523 |
| `_internal/tokenizers/tokenizers.pyd` | 7,395,328 | 7.053 |
| `_internal/libcrypto-3-x64.dll` | 7,349,064 | 7.009 |
| `_internal/torchvision/_C.pyd` | 7,343,104 | 7.003 |
| `_internal/pypdfium2_raw/pdfium.dll` | 7,260,672 | 6.924 |
| `_internal/scipy/optimize/_highspy/_core.cp311-win_amd64.pyd` | 6,436,864 | 6.139 |
| `_internal/torch/lib/nvrtc-builtins64_128.dll` | 6,356,480 | 6.062 |
| `_internal/python311.dll` | 6,177,096 | 5.891 |
| `_internal/torchvision/python311.dll` | 6,177,096 | 5.891 |
| `_internal/torchvision/nvjpeg64_12.dll` | 6,171,648 | 5.886 |
| `_internal/pydantic_core/_pydantic_core.cp311-win_amd64.pyd` | 5,148,672 | 4.910 |
| `_internal/numpy/_core/_multiarray_umath.cp311-win_amd64.pyd` | 4,520,960 | 4.312 |
| `_internal/torch/lib/cupti64_2025.1.1.dll` | 4,483,664 | 4.276 |
| `_internal/scipy/sparse/_sparsetools.cp311-win_amd64.pyd` | 4,114,944 | 3.924 |
| `_internal/torch/lib/cudnn_cnn64_9.dll` | 2,984,560 | 2.846 |
| `_internal/scipy/io/_fast_matrix_market/_fmm_core.cp311-win_amd64.pyd` | 2,842,624 | 2.711 |
| `_internal/torch/bin/protoc.exe` | 2,800,640 | 2.671 |
| `_internal/PIL/_imaging.cp311-win_amd64.pyd` | 2,632,704 | 2.511 |

## Top 30 largest directories

| Directory | Bytes | MiB |
|---|---:|---:|
| `_internal` | 5,214,671,717 | 4,973.098 |
| `_internal/torch` | 4,276,956,018 | 4,078.823 |
| `_internal/torch/lib` | 4,231,437,536 | 4,035.413 |
| `_internal/paddle` | 322,655,988 | 307.709 |
| `_internal/paddle/libs` | 195,805,940 | 186.735 |
| `_internal/_polars_runtime_32` | 175,884,800 | 167.737 |
| `_internal/paddle/base` | 126,850,048 | 120.974 |
| `_internal/cv2` | 116,231,880 | 110.847 |
| `_internal/scipy` | 55,299,072 | 52.737 |
| `_internal/transformers` | 46,151,934 | 44.014 |
| `_internal/transformers/models` | 39,916,281 | 38.067 |
| `_internal/torchvision` | 24,188,137 | 23.068 |
| `_internal/numpy.libs` | 20,978,768 | 20.007 |
| `_internal/scipy.libs` | 20,260,864 | 19.322 |
| `_internal/matplotlib` | 14,340,082 | 13.676 |
| `_internal/PIL` | 13,422,080 | 12.800 |
| `_internal/pandas` | 13,003,924 | 12.402 |
| `_internal/pandas/_libs` | 12,995,072 | 12.393 |
| `_internal/sklearn` | 12,950,418 | 12.350 |
| `_internal/scipy/optimize` | 10,375,680 | 9.895 |
| `_internal/scipy/special` | 10,252,800 | 9.778 |
| `_internal/cryptography/hazmat/bindings` | 9,943,040 | 9.482 |
| `_internal/cryptography/hazmat` | 9,943,040 | 9.482 |
| `_internal/cryptography` | 9,943,040 | 9.482 |
| `_internal/matplotlib/mpl-data` | 9,648,626 | 9.202 |
| `_internal/hf_xet` | 9,499,136 | 9.059 |
| `_internal/matplotlib/mpl-data/fonts` | 8,884,861 | 8.473 |
| `_internal/torch/_inductor` | 8,587,584 | 8.190 |
| `_internal/scipy/optimize/_highspy` | 7,717,376 | 7.360 |
| `_internal/scipy/linalg` | 7,527,936 | 7.179 |

## Largest extension groups

| Extension | Bytes | MiB |
|---|---:|---:|
| `.dll` | 4,545,682,644 | 4,335.101 |
| `.pyd` | 546,130,423 | 520.831 |
| `.exe` | 98,495,104 | 93.932 |
| `.py` | 94,335,762 | 89.966 |
| `.ttf` | 7,510,312 | 7.162 |
| `<none>` | 5,263,982 | 5.020 |
| `.json` | 2,599,408 | 2.479 |
| `.enc` | 1,514,059 | 1.444 |
| `.zip` | 1,443,233 | 1.376 |
| `.afm` | 1,363,429 | 1.300 |
| `.tcl` | 928,194 | 0.885 |
| `.yaml` | 800,040 | 0.763 |
| `.bin` | 752,804 | 0.718 |
| `.pyx` | 725,789 | 0.692 |
| `.jpg` | 588,792 | 0.562 |
| `.tp` | 479,222 | 0.457 |
| `.gz` | 392,378 | 0.374 |
| `.txt` | 349,481 | 0.333 |
| `.tm` | 271,012 | 0.258 |
| `.npz` | 242,130 | 0.231 |
