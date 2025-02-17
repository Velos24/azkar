// إيقاف الأنميشن بعد تنفيذه مرة واحدة
document.addEventListener("DOMContentLoaded", function () {
    const animatedElements = document.querySelectorAll(".animated-link, .about, .footer-item");

    animatedElements.forEach(element => {
        element.style.animationPlayState = "running";
        setTimeout(() => {
            element.style.animationPlayState = "paused"; // إيقاف الأنميشن بعد تنفيذه
        }, 2000); // الوقت بالمللي ثانية (2 ثانية)
    });
});
