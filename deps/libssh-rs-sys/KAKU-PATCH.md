Vendored from the crates.io libssh-rs-sys 0.2.6 package.
Package SHA-256: 01d528ea9ac190fa364ff12193da82222dfc645e7ab28666ae91493bd288a1a0.

Local change: use crypto/ssl for Windows GNU, retaining libcrypto/libssl
for MSVC in build.rs. The native library and existing license notices are
preserved. This avoids asking MinGW for liblibcrypto.a and liblibssl.a.
