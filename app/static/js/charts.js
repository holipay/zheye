/**
 * 者也 - 图表工具函数
 * 基于 Chart.js
 */

const ChartUtils = {
    // 默认颜色配置
    colors: {
        primary: '#1a1a2e',
        secondary: '#16213e',
        accent: '#e94560',
        success: '#00b894',
        warning: '#fdcb6e',
        purple: '#6c5ce7',
        blue: '#0984e3',
        gray: '#78909c',
    },

    // 图表颜色数组
    colorPalette: [
        '#e94560', '#00b894', '#6c5ce7', '#fdcb6e', '#00cec9',
        '#fd79a8', '#a29bfe', '#55efc4', '#ff7675', '#74b9ff'
    ],

    // 默认图表选项
    defaultOptions: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: {
                    padding: 16,
                    usePointStyle: true,
                    font: {
                        family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                        size: 12
                    }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(26, 26, 46, 0.9)',
                titleFont: {
                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                    size: 13
                },
                bodyFont: {
                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                    size: 12
                },
                padding: 12,
                cornerRadius: 6
            }
        }
    },

    /**
     * 创建折线图
     */
    createLineChart(ctx, labels, datasets, options = {}) {
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                ...this.defaultOptions,
                ...options,
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                                size: 11
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0,0,0,0.05)'
                        },
                        ticks: {
                            font: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                                size: 11
                            }
                        }
                    }
                }
            }
        });
    },

    /**
     * 创建柱状图
     */
    createBarChart(ctx, labels, values, options = {}) {
        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: this.colorPalette.slice(0, values.length),
                    borderRadius: 4,
                    barThickness: 'flex'
                }]
            },
            options: {
                ...this.defaultOptions,
                ...options,
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                                size: 11
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0,0,0,0.05)'
                        },
                        ticks: {
                            font: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif",
                                size: 11
                            }
                        }
                    }
                }
            }
        });
    },

    /**
     * 创建水平柱状图
     */
    createHorizontalBarChart(ctx, labels, values, options = {}) {
        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: this.colorPalette.slice(0, values.length),
                    borderRadius: 4
                }]
            },
            options: {
                ...this.defaultOptions,
                ...options,
                indexAxis: 'y',
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0,0,0,0.05)'
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    },

    /**
     * 创建饼图/环形图
     */
    createPieChart(ctx, labels, values, colors, options = {}) {
        return new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors || this.colorPalette.slice(0, values.length),
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                ...this.defaultOptions,
                ...options,
                cutout: '65%',
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        ...this.defaultOptions.plugins.legend,
                        position: 'bottom'
                    }
                }
            }
        });
    },

    /**
     * 创建面积图
     */
    createAreaChart(ctx, labels, datasets, options = {}) {
        const areaDatasets = datasets.map((dataset, index) => ({
            ...dataset,
            fill: true,
            backgroundColor: dataset.backgroundColor || (this.colorPalette[index] + '20'),
            borderColor: dataset.borderColor || this.colorPalette[index],
            tension: 0.3
        }));

        return this.createLineChart(ctx, labels, areaDatasets, options);
    },

    /**
     * 从 API 加载数据并创建图表
     */
    async loadAndCreate(url, createFn, containerId) {
        try {
            const response = await fetch(url);
            const data = await response.json();
            const container = document.getElementById(containerId);
            
            if (!container) return null;
            
            // 创建 canvas
            const canvas = document.createElement('canvas');
            container.innerHTML = '';
            container.appendChild(canvas);
            
            return createFn(canvas.getContext('2d'), data);
        } catch (error) {
            console.error(`加载图表数据失败: ${url}`, error);
            return null;
        }
    },

    /**
     * 格式化数字
     */
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
};

// 导出
window.ChartUtils = ChartUtils;
