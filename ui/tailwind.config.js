/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                brand: {
                    // Document Blue baseline
                    blue: {
                        deep: "#0F172A",     // Dark background canvas
                        surface: "#1E293B",  // Card components / chat boxes
                        accent: "#1E3A8A",   // Solid button lines
                        glow: "#3B82F6"      // Focus rings
                    },
                    // Warning Yellow - Used for time/OTel telemetry execution indicators
                    yellow: {
                        bright: "#EAB308",
                        muted: "#CA8A04"
                    },
                    // PDF Red - Reserved for errors, deletion UI, and performance threshold spikes
                    red: {
                        core: "#DC2626",
                        light: "#FEF2F2"
                    }
                }
            }
        },
    },
    plugins: [],
}