document.querySelector('.logo').addEventListener('click', function () {
    this.style.animation = 'none'; // إيقاف الأنميشن الحالي
    void this.offsetWidth; // إعادة تحميل الأنميشن
    this.style.animation = 'shake 0.5s'; // تشغيل الأنميشن مرة أخرى
});
