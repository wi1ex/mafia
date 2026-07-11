<template>
  <svg
    class="ui-loader-icon"
    viewBox="0 0 64 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <circle cx="32" cy="8" r="2.6667" />
    <circle cx="49" cy="15" r="3.3333" />
    <circle cx="56" cy="32" r="4" />
    <circle cx="49" cy="49" r="4.6667" />
    <circle cx="32" cy="56" r="5.3333" />
    <circle cx="15" cy="49" r="6" />
    <circle cx="8" cy="32" r="6.6667" />
    <circle cx="15" cy="15" r="7.3333" />
  </svg>
</template>

<style scoped lang="scss">
.ui-loader-icon {
  display: inline-block;
  flex: 0 0 auto;
  width: var(--ui-icon-width, 48px);
  height: var(--ui-icon-height, 48px);
  color: var(--ui-icon-color, currentColor);
  animation: loader-spin 1.2s linear infinite;
  transform-origin: center;
  circle {
    fill: currentColor;
    transform-origin: center;
    animation: loader-pulse 1.2s ease-in-out infinite;
  }
  circle:nth-child(1) {
    animation-delay: 0s;
  }
  circle:nth-child(2) {
    animation-delay: 0.1s;
  }
  circle:nth-child(3) {
    animation-delay: 0.2s;
  }
  circle:nth-child(4) {
    animation-delay: 0.3s;
  }
  circle:nth-child(5) {
    animation-delay: 0.4s;
  }
  circle:nth-child(6) {
    animation-delay: 0.5s;
  }
  circle:nth-child(7) {
    animation-delay: 0.6s;
  }
  circle:nth-child(8) {
    animation-delay: 0.7s;
  }
}

@keyframes loader-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes loader-pulse {
  0%,
  100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ui-loader-icon {
    animation-duration: 2.5s;
    circle {
      animation-duration: 2.5s;
    }
  }
}

</style>
