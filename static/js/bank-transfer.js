/* =========================================
   Bank Transfer Page
   فرم به‌صورت POST معمولی به سرور ارسال می‌شود (POST → Redirect → GET).
   این اسکریپت فقط پیش‌نمایش تصویر فیش را مدیریت می‌کند.
========================================= */


/* =========================================
   DOM Elements
========================================= */

const receiptFile =
    document.getElementById("receiptFile");

const fileInputIcon =
    document.getElementById("fileInputIcon");

const fileInputText =
    document.getElementById("fileInputText");

const filePreview =
    document.getElementById("filePreview");

const filePreviewImage =
    document.getElementById("filePreviewImage");


/* =========================================
   File Input Handler (preview)
========================================= */

if (receiptFile) {

    receiptFile.addEventListener(
        "change",
        (event) => {

            const file =
                event.target.files[0];

            if (!file) {
                return;
            }

            if (fileInputIcon) {
                fileInputIcon.textContent = "✓";
            }

            if (fileInputText) {
                fileInputText.textContent = file.name;
            }

            // نمایش پیش‌نمایش

            const reader =
                new FileReader();

            reader.onload =
                (e) => {

                    if (filePreviewImage) {
                        filePreviewImage.src = e.target.result;
                    }

                    if (filePreview) {
                        filePreview.classList.remove("hidden");
                    }
                };

            reader.readAsDataURL(file);

        }
    );
}
