# Runtime Size Audit

Generated: `2026-09-23T14:20:22.364411+00:00`

Reference Runtime: `748,413,790` bytes (`0.697 GiB`), `2,850` files.

## Component breakdown

| Component | Bytes | MiB | Share |
|---|---:|---:|---:|
| Paddle | 322,655,988 | 307.709 | 43.112% |
| Others | 180,070,834 | 171.729 | 24.060% |
| OpenCV | 116,231,880 | 110.847 | 15.530% |
| SciPy | 70,748,160 | 67.471 | 9.453% |
| NumPy | 28,174,515 | 26.869 | 3.765% |
| Transformers/Hugging Face | 16,894,464 | 16.112 | 2.257% |
| scikit-learn | 12,950,418 | 12.350 | 1.730% |
| PaddleX | 687,531 | 0.656 | 0.092% |

## Top 50 largest files

| File | Bytes | MiB |
|---|---:|---:|
| `_internal/paddle/base/libpaddle.pyd` | 126,850,048 | 120.974 |
| `_internal/paddle/libs/mklml.dll` | 92,649,344 | 88.357 |
| `_internal/cv2/cv2.pyd` | 89,814,528 | 85.654 |
| `visionguard-core-runtime.exe` | 49,006,463 | 46.736 |
| `_internal/paddle/libs/mkldnn.dll` | 47,322,112 | 45.130 |
| `_internal/paddle/libs/phi.dll` | 42,797,056 | 40.814 |
| `_internal/cv2/opencv_videoio_ffmpeg4100_64.dll` | 26,391,552 | 25.169 |
| `_internal/numpy.libs/libscipy_openblas64_-9e3e5a4229c1ca39f10dc82bba9e2b2b.dll` | 20,403,712 | 19.458 |
| `_internal/scipy.libs/libscipy_openblas-64eda39e79589aedb16f58e5547eb599.dll` | 20,260,864 | 19.322 |
| `_internal/onnxruntime/capi/onnxruntime_pybind11_state.pyd` | 17,548,088 | 16.735 |
| `_internal/onnxruntime/capi/onnxruntime.dll` | 16,401,208 | 15.641 |
| `_internal/cryptography/hazmat/bindings/_rust.pyd` | 9,943,040 | 9.482 |
| `_internal/hf_xet/hf_xet.pyd` | 9,499,136 | 9.059 |
| `_internal/paddle/libs/liblapack.dll` | 7,895,054 | 7.529 |
| `_internal/PIL/_avif.cp311-win_amd64.pyd` | 7,888,896 | 7.523 |
| `_internal/tokenizers/tokenizers.pyd` | 7,395,328 | 7.053 |
| `_internal/libcrypto-3-x64.dll` | 7,349,064 | 7.009 |
| `_internal/pypdfium2_raw/pdfium.dll` | 7,260,672 | 6.924 |
| `_internal/scipy/optimize/_highspy/_core.cp311-win_amd64.pyd` | 6,436,864 | 6.139 |
| `_internal/python311.dll` | 6,177,096 | 5.891 |
| `_internal/pydantic_core/_pydantic_core.cp311-win_amd64.pyd` | 5,148,672 | 4.910 |
| `_internal/numpy/_core/_multiarray_umath.cp311-win_amd64.pyd` | 4,520,960 | 4.312 |
| `_internal/scipy/sparse/_sparsetools.cp311-win_amd64.pyd` | 4,114,944 | 3.924 |
| `_internal/PIL/_imaging.cp311-win_amd64.pyd` | 2,632,704 | 2.511 |
| `_internal/Shapely.libs/geos-ae6efa0782962b98e358f10ea539ae5f.dll` | 2,564,608 | 2.446 |
| `_internal/scipy/special/_ufuncs_cxx.cp311-win_amd64.pyd` | 2,404,864 | 2.293 |
| `_internal/scipy/special/_special_ufuncs.cp311-win_amd64.pyd` | 2,292,224 | 2.186 |
| `_internal/scipy/linalg/_flapack.cp311-win_amd64.pyd` | 2,266,624 | 2.162 |
| `_internal/scipy/special/cython_special.cp311-win_amd64.pyd` | 2,185,216 | 2.084 |
| `_internal/PIL/_imagingft.cp311-win_amd64.pyd` | 2,174,464 | 2.074 |
| `_internal/tcl86t.dll` | 1,842,504 | 1.757 |
| `_internal/paddle/libs/libiomp5md.dll` | 1,726,848 | 1.647 |
| `_internal/pandas/_libs/groupby.cp311-win_amd64.pyd` | 1,677,824 | 1.600 |
| `_internal/sqlite3.dll` | 1,677,128 | 1.599 |
| `_internal/tk86t.dll` | 1,582,408 | 1.509 |
| `_internal/scipy/spatial/_ckdtree.cp311-win_amd64.pyd` | 1,529,856 | 1.459 |
| `_internal/pandas/_libs/hashtable.cp311-win_amd64.pyd` | 1,528,832 | 1.458 |
| `_internal/scipy/special/_gufuncs.cp311-win_amd64.pyd` | 1,515,008 | 1.445 |
| `_internal/base_library.zip` | 1,443,233 | 1.376 |
| `_internal/pandas/_libs/algos.cp311-win_amd64.pyd` | 1,394,688 | 1.330 |
| `_internal/scipy/special/_ufuncs.cp311-win_amd64.pyd` | 1,391,104 | 1.327 |
| `_internal/scipy/spatial/_distance_pybind.cp311-win_amd64.pyd` | 1,361,408 | 1.298 |
| `_internal/libssl-3-x64.dll` | 1,326,920 | 1.265 |
| `_internal/paddle/libs/libgfortran-3.dll` | 1,316,352 | 1.255 |
| `_internal/scipy/optimize/_highspy/_highs_options.cp311-win_amd64.pyd` | 1,280,512 | 1.221 |
| `_internal/sklearn/_loss/_loss.cp311-win_amd64.pyd` | 1,249,792 | 1.192 |
| `_internal/scipy/interpolate/_rbfinterp_pythran.cp311-win_amd64.pyd` | 1,165,312 | 1.111 |
| `_internal/unicodedata.pyd` | 1,140,552 | 1.088 |
| `_internal/ucrtbase.dll` | 1,123,808 | 1.072 |
| `_internal/scipy/fft/_pocketfft/pypocketfft.cp311-win_amd64.pyd` | 1,118,208 | 1.066 |

## Top 30 largest directories

| Directory | Bytes | MiB |
|---|---:|---:|
| `_internal` | 698,857,544 | 666.482 |
| `_internal/paddle` | 322,655,988 | 307.709 |
| `_internal/paddle/libs` | 195,805,940 | 186.735 |
| `_internal/paddle/base` | 126,850,048 | 120.974 |
| `_internal/cv2` | 116,231,880 | 110.847 |
| `_internal/scipy` | 50,487,296 | 48.148 |
| `_internal/onnxruntime/capi` | 33,971,112 | 32.397 |
| `_internal/onnxruntime` | 33,971,112 | 32.397 |
| `_internal/numpy.libs` | 20,978,768 | 20.007 |
| `_internal/scipy.libs` | 20,260,864 | 19.322 |
| `_internal/PIL` | 13,422,080 | 12.800 |
| `_internal/pandas` | 13,003,924 | 12.402 |
| `_internal/pandas/_libs` | 12,995,072 | 12.393 |
| `_internal/sklearn` | 12,950,418 | 12.350 |
| `_internal/scipy/optimize` | 10,375,680 | 9.895 |
| `_internal/scipy/special` | 10,252,800 | 9.778 |
| `_internal/cryptography/hazmat/bindings` | 9,943,040 | 9.482 |
| `_internal/cryptography/hazmat` | 9,943,040 | 9.482 |
| `_internal/cryptography` | 9,943,040 | 9.482 |
| `_internal/hf_xet` | 9,499,136 | 9.059 |
| `_internal/scipy/optimize/_highspy` | 7,717,376 | 7.360 |
| `_internal/scipy/linalg` | 7,527,936 | 7.179 |
| `_internal/scipy/sparse` | 7,414,272 | 7.071 |
| `_internal/tokenizers` | 7,395,328 | 7.053 |
| `_internal/pypdfium2_raw` | 7,260,824 | 6.924 |
| `_internal/numpy` | 6,959,616 | 6.637 |
| `_internal/pydantic_core` | 5,148,672 | 4.910 |
| `_internal/scipy/spatial` | 4,847,104 | 4.623 |
| `_internal/numpy/_core` | 4,583,936 | 4.372 |
| `_internal/scipy/interpolate` | 3,834,880 | 3.657 |

## Largest extension groups

| Extension | Bytes | MiB |
|---|---:|---:|
| `.pyd` | 370,027,823 | 352.886 |
| `.dll` | 316,493,420 | 301.832 |
| `.exe` | 49,006,463 | 46.736 |
| `<none>` | 2,684,684 | 2.560 |
| `.enc` | 1,514,059 | 1.444 |
| `.zip` | 1,443,233 | 1.376 |
| `.json` | 1,077,846 | 1.028 |
| `.tcl` | 928,194 | 0.885 |
| `.bin` | 752,804 | 0.718 |
| `.pyx` | 725,789 | 0.692 |
| `.tp` | 479,222 | 0.457 |
| `.yaml` | 460,171 | 0.439 |
| `.gz` | 359,149 | 0.343 |
| `.jpg` | 339,640 | 0.324 |
| `.txt` | 334,172 | 0.319 |
| `.tm` | 271,012 | 0.258 |
| `.pem` | 240,216 | 0.229 |
| `.msg` | 192,304 | 0.183 |
| `.cpp` | 172,212 | 0.164 |
| `.lib` | 145,228 | 0.139 |
