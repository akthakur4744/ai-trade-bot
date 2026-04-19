# **Comprehensive Architecture for Autonomous Equity Trading: A Multi-Dimensional Analysis of Alpha Generation, Systematic Risk Management, and LLM-Driven Execution**

The shift from discretionary to systematic trading represents one of the most significant paradigm shifts in financial history, transitioning the locus of decision-making from human intuition to quantitative rigor. For an autonomous agent utilizing advanced large language models such as Claude, the construction of a successful trading system requires a synthesized understanding of market parameters that extend across technical, fundamental, and alternative data domains. Historically, trading success has been predicated on a tripartite foundation: a proven method (edge), rigorous risk management (capital preservation), and unwavering discipline (psychological execution).1 In the context of automated agents, this discipline is codified through rule-based logic, effectively neutralizing the emotional biases—such as fear, greed, and overconfidence—that typically derail human participants.3

Empirical data suggests that approximately 95% of retail traders fail to achieve long-term profitability, a failure often attributed to the absence of a verifiable edge or the inability to manage risk effectively.2 The development of a Claude-based agent offers the potential to transcend these limitations by processing high-dimensional data at speeds and scales impossible for humans, leveraging the Model Context Protocol (MCP) to integrate directly with live market feeds and execution brokers.6 Success in this endeavor is not the result of a single "holy grail" indicator but is instead found in the orchestrated interaction of diverse parameters, calibrated to specific market regimes and protected by robust mathematical risk controls.9

## **Technical Parameters: Oscillators, Trend Indicators, and the Hierarchy of Reliability**

Technical analysis operates on the core assumption that price and volume data serve as a leading proxy for all available information and collective market psychology. The efficacy of technical indicators is often debated, yet extensive longitudinal backtesting—covering periods from the late 19th century to the present—reveals consistent patterns of nonlinear predictability in equity returns.12 When an agent evaluates stocks, technical parameters provide the critical "when" of the trade, identifying moments of momentum expansion or mean-reversion exhaustion.

### **Comparative Reliability and Performance Metrics**

The reliability of technical indicators can be categorized by their win rates and their average gain-to-loss ratios. High-win-rate indicators, such as the Relative Strength Index (RSI) or Bollinger Bands, often provide frequent small successes but can suffer from large tail-risk events if not managed correctly.13 Conversely, trend-following indicators like Simple Moving Averages (SMA) exhibit lower win rates—often below 35%—but capture the significant trending moves that drive overall portfolio profitability.13

| Technical Indicator | Historical Win Rate (%) | Average Gain/Loss Ratio | Performance Classification |
| :---- | :---- | :---- | :---- |
| Relative Strength Index (RSI) | 79.4 | 0.77 | Most Reliable (Signal Frequency) |
| Bollinger Bands (BB) | 77.8 | 0.72 | High Probability Mean Reversion |
| Donchian Channels | 74.1 | 0.71 | Range Breakdown/Breakout |
| Williams %R (WPR) | 71.7 | 0.70 | Overbought/Oversold Consistency |
| ADX (14) | 53.6 | 1.21 | Trend Strength Confirmation |
| Stochastics | 44.9 | 1.63 | Momentum Reversal Timing |
| Ichimoku Cloud | 42.3 | 2.11 | Comprehensive Trend Analysis |
| MACD (12, 26, 9\) | 40.1 | 2.01 | Trend Momentum Following |
| EMA (50) | 30.7 | 3.34 | High-Performance Trend Filter |
| SMA (50) | 28.6 | 4.14 | Highest Total Return Potential |

The data implies a structural trade-off between reliability (win rate) and efficiency (gain/loss ratio). For instance, the SMA (50) yields a win rate of only 28.6%, yet its gain/loss ratio of 4.14 indicates that each successful trade earns more than four times the amount lost on a failed trade.13 An agent must therefore be programmed to tolerate a high frequency of small losses to capture the infrequent but substantial gains that characterize successful trend-following.2

### **The Mechanism of Indicator Synergy**

Relying on a single technical parameter is hazardous, as oscillators like the RSI are prone to "pegging" at extreme levels during strong trends, leading to premature exit or disastrous counter-trend entry.12 The superior approach involves a multi-indicator confirmation strategy. In the Indian equity markets, for example, research has demonstrated that combining the Supertrend indicator with RSI and EMA leads to performance that significantly exceeds any individual tool.12 This synergy functions by using the EMA as a broad trend filter, the Supertrend as the primary entry signal, and the RSI to ensure the entry is not made at an overextended price point.12

Mathematical precision is essential for these signals. The RSI, for instance, is a momentum oscillator that measures the speed and change of price movements, calculated as:

![][image1]  
where the average gain and loss are calculated over a look-back period (standardly 14 bars).12 An agent can utilize Claude’s ability to interpret these mathematical thresholds alongside price action to detect "divergences"—situations where the price makes a new high but the RSI does not, signaling a potential reversal in momentum before it is visible in the price itself.18

## **Fundamental Parameters: The "What" of Selection and Value Synergies**

If technical indicators provide the timing, fundamental parameters provide the "what"—the specific selection of stocks that possess the requisite financial health to sustain a move. Fundamental analysis seeks to determine a company's intrinsic value by evaluating its financial statements, market position, and management effectiveness.20 For an automated agent, these parameters act as a crucial preliminary filter, ensuring the system does not waste capital on "value traps" or companies with high insolvency risk.21

### **Primary Financial Ratios and Return Correlation**

Empirical studies on stock returns show that certain fundamental factors have a higher predictive value than others. Metrics like Return on Assets (ROA), Earnings Per Share (EPS), and the Current Ratio are consistently associated with positive stock performance.22 Conversely, high Debt-to-Equity (D/E) ratios are often negatively correlated with returns, as leverage increases a firm’s vulnerability to economic shocks.23

| Fundamental Parameter | Relationship to Return | Significance in Selection |
| :---- | :---- | :---- |
| Earnings Per Share (EPS) | Strongly Positive | Primary driver of investor valuation.22 |
| Return on Assets (ROA) | Positive | Measures asset utilization efficiency.23 |
| Current Ratio | Positive | Proxy for short-term liquidity and survival.22 |
| Debt-to-Equity (D/E) | Negative | High leverage indicates elevated solvency risk.22 |
| Price-to-Earnings (P/E) | Positive/Variable | Higher ratios often reflect growth expectations.23 |
| Price-to-Book (P/B) | Neutral/Weak | Traditional value metric with declining efficacy.20 |
| Firm Size (Total Assets) | Positive | Correlated with stability and institutional support.22 |

The importance of EPS cannot be overstated; it represents a company's ability to generate earnings per outstanding share and is the primary metric institutional investors scrutinize during quarterly reports.22 An agent that filters for stocks with positive EPS growth and a healthy current ratio (above 1.0) significantly reduces its exposure to bankruptcies and severe liquidity events.22

### **Integrating Quality and Value: FSCORE and GSCORE Frameworks**

A sophisticated agent should not look at fundamental factors in isolation. The integration of "quality" (financial strength) and "value" (attractive pricing) provides a more robust alpha source. The Piotroski FSCORE is a nine-point scale that assesses a firm's profitability, leverage, and operating efficiency. When combined with a value metric like the Value-to-Price (V/P) ratio, the resulting "hedge" returns—longing the best quintile and shorting the worst—drastically outperform standalone strategies.21

| Strategy Type | Annual Hedge Return (%) | Combined Strategy Return (%) |
| :---- | :---- | :---- |
| FSCORE (Quality-Driven) | 7.44 | \- |
| V/P (Value-Driven) | 6.55 | \- |
| FSCORE \+ V/P | \- | 17.94 |
| GSCORE (Growth-Quality) | 6.06 | \- |
| GSCORE \+ V/P | \- | 21.45 |

This synergy addresses a critical market anomaly: quality firms are often expensive, and cheap firms are often low-quality. By identifying "Quality at a Reasonable Price" (QARP), an agent can isolate stocks that the market has undervalued despite their strong underlying fundamentals.21 This approach is particularly effective for value stocks (high book-to-market), where FSCORE provides the necessary filter to avoid distressed companies.21

## **Systematic Factor Investing: Diversification through Quantifiable Traits**

Beyond individual company ratios, institutional research—most notably from AQR Capital Management and Fama-French—identifies systematic "factors" or "styles" that drive returns across broad market cycles.25 These factors include Value, Momentum, Quality, Size, and Low Volatility. The success of factor investing lies in the fact that these styles often have low or negative correlations with one another, providing a "holy grail" of portfolio construction where the overall Sharpe ratio is higher than that of any single factor.26

### **The Multi-Factor Advantage**

The Fama-French five-factor model is the academic standard for evaluating these premiums. It posits that stock returns can be explained by exposure to market risk, size (small caps), value (high book-to-market), profitability (robust margins), and investment (conservative asset growth).28

| Investment Factor | Systematic Driver | Correlation with Other Factors |
| :---- | :---- | :---- |
| Value | Mean reversion of undervalued assets | Negatively correlated with Momentum.26 |
| Momentum | Persistence of established price trends | Negatively correlated with Value.26 |
| Quality | Profitability and balance sheet strength | Low correlation with Market Beta.25 |
| Low Volatility | Defensive stocks with stable returns | Useful for drawdown mitigation.25 |
| Size | Premium for holding smaller, less-liquid firms | Variable across economic regimes.28 |

AQR’s research highlights that while individual factors like Value can experience prolonged periods of underperformance—such as the "zeroth percentile" event in early 2020—a disciplined commitment to a diversified factor portfolio allows for the eventual capture of long-term premia.26 An autonomous agent can dynamically tilt its exposure between these factors based on the economic environment, using Quality and Low Volatility in recessionary phases and Momentum in expansionary phases.25

## **Alternative Data and LLM-Driven Sentiment Analysis: The Modern Alpha Frontier**

In an era of highly efficient markets, traditional technical and fundamental data are often priced in almost instantaneously. Alpha is increasingly found in alternative data—non-traditional datasets such as satellite imagery, web-scraped job postings, credit card transactions, and social media sentiment.29 For a Claude-based agent, the primary advantage lies in its ability to perform high-fidelity sentiment analysis on unstructured news and social feeds, transforming textual "noise" into actionable trading signals.6

### **Sentiment Analysis and Sentiment Gates**

Claude’s capability to analyze sentiment involves more than just a binary "good/bad" classification. Models like Claude Haiku can process news feeds (e.g., Reddit, CNBC, Finnhub) to generate structured JSON outputs that include sentiment scores, urgency levels, and confidence intervals.6 These scores can be used as a "gate" to confirm technical signals; for instance, a technical "buy" signal might only be executed if the 24-hour sentiment score for the ticker is above 0.65.6

| Alternative Data Source | Alpha Insight Potential | Monitoring Focus |
| :---- | :---- | :---- |
| News & Press Releases | Immediate sentiment impact | Earnings, M\&A activity, regulatory shifts.6 |
| Social Media (Reddit/X) | Retail crowd-sourced momentum | Identifying "meme" stock bubbles and retail flow.33 |
| Satellite Imagery | Real-time economic activity | Retail parking lot counts, shipping port traffic.31 |
| Web Scraping (Job Postings) | Hidden corporate growth signals | Expansion into new markets or technologies.31 |
| Credit Card Microdata | Consumer spending trends | Early detection of retail earnings beats/misses.30 |

The monetary value of alternative data depends heavily on the investor’s style and the "excludability" of the data. As more participants gain access to a dataset, the alpha it provides decays.29 However, using an LLM to derive *unique* insights from publicly available but unstructured text (like earnings transcripts) remains a defensible edge.31 A news-based trading agent powered by Claude Haiku demonstrated the practical utility of this approach, achieving a profitable week on a paper account by focusing on volatile, news-sensitive stocks and employing trailing stops to lock in sentiment-driven gains.6

## **Market Regime Detection: The Contextual Filter for Success**

A strategy’s success is often contingent upon the market regime—the prevailing environment of volatility and price direction. A strategy that excels in a low-volatility, trending bull market (like trend-following) will often suffer severe losses in a high-volatility, range-bound market (choppy sideways action).10 Market regime detection involves identifying these shifts to adjust or pause the agent's trading activity.10

### **Advanced Algorithms for Regime Classification**

Traditional moving average crossovers (e.g., price above the 200-day SMA) are common filters but are inherently lagging.10 More sophisticated approaches utilize machine learning to classify regimes based on distributions of returns and volatility.

* **Hidden Markov Models (HMM):** HMMs assume that the market transitions between "hidden" states (e.g., low-volatility bull, high-volatility bear) that aren't directly observable but can be inferred from price returns. Fitting an HMM to SPY returns allows an agent to disallow trades during predicted high-volatility states, significantly improving the risk-adjusted return (Sharpe Ratio).36  
* **Wasserstein K-Means Clustering:** Standard K-Means clustering often fails in finance because it ignores the temporal and distributional nature of returns. Using the Wasserstein distance (or "Earth Mover's Distance") to cluster distributions allows for the detection of regime shifts that K-Means would miss, clearly separating calm consolidation phases from aggressive price trends.35  
* **Market Breadth and VIX Term Structure:** Regime detection can also be informed by external market context. Breadth indicators—such as the percentage of stocks above their 50-day moving average—can signal a deteriorating market even while index prices remain high.10 Additionally, the VIX/VIX3M ratio is a powerful regime input: a ratio above 1.0 indicates "backwardation" in volatility futures, a hallmark of acute market stress where mean-reversion strategies often fail.10

| Market State | Key Characteristic | Ideal Parameter Tuning |
| :---- | :---- | :---- |
| Trending Low-Vol | Consistent higher highs, low VIX | Aggressive trend-following, loose stops.10 |
| Trending High-Vol | Sharp moves, wide ATR | Tighter stops, reduced position sizing.10 |
| Mean Reverting | Range-bound, oscillating RSI | Mean-reversion oscillators (RSI, Stochastics).10 |
| Sideways Chop | Non-directional, high noise | Halt trading; move to cash.10 |

The primary insight for an agent is that "bad trades" are often not the result of a faulty signal, but a signal applied to the wrong environment.10 By scoring the market environment on direction, agreement across timeframes, and volatility structure before entry, an agent can significantly increase its success rate.10

## **The AI Agent Architecture: Building with Claude and MCP**

Developing a trading agent with Claude involves more than writing a prompt; it requires a robust technical architecture that connects the LLM to live data feeds and execution engines. The Model Context Protocol (MCP) is the foundational bridge for this integration.6

### **Integrating External Tools via MCP**

MCP allows Claude to access external "tools"—Python functions or API wrappers—that provide real-time information. For a trading system, these tools typically include:

1. **Market Data Tools:** Fetching live quotes, historical OHLC (Open, High, Low, Close) data, and technical indicator values via providers like AlphaVantage or Polygon.io.39  
2. **Broker Integration:** Connecting to Alpaca or Interactive Brokers to check account balances, calculate buying power, and place orders.8  
3. **Semantic Search (RAG):** Using a vector database to search through news headlines and social sentiment, allowing the agent to "remember" previous market events.8

### **Multi-Agent Coordination Patterns**

To manage the complexity of market analysis, a multi-agent architecture is often more effective than a single monolithic prompt.8

* **The Orchestrator:** This agent (Claude 3.5 Sonnet or Opus) receives the user’s goal and decides which specialized analysts to consult.8  
* **The Analysts:** Specialized sub-agents for Technical, Fundamental, and Sentiment analysis. Each analyst has a dedicated system prompt and set of MCP tools.8  
* **The Debate Protocol:** A deterministic workflow where a "Bull Agent" presents the case for a trade, a "Bear Agent" identifies the risks, and a "Judge Agent" synthesizes the arguments into a final TradeRecommendation (Buy/Sell/Pass) with a confidence score.8

This modular approach allows for "Plan Mode" (/plan), where the agent reviews the proposed trading logic and codebase for conflicts or biases before execution.6 Furthermore, using Claude's persistent memory (such as a CLAUDE.md project file) ensures the agent maintains consistency in its risk rules and architectural constraints across different sessions.6

## **Market Microstructure and Execution: Navigating the Liquidity Maze**

Profitability is frequently lost not in the strategy design, but in the execution. Market microstructure—the study of how orders are matched and how liquidity flows—is critical for ensuring that an agent's paper-trading results translate into live-trading success.40

### **Liquidity, Slippage, and Smart Execution**

Liquidity is the market's ability to absorb an order without significant price impact. In liquid markets, the bid-ask spread is tight, whereas in illiquid markets, the act of buying can "push" the price higher, resulting in poor entry prices (slippage).24

| Microstructure Factor | Impact on Profitability | Mitigation Strategy |
| :---- | :---- | :---- |
| Bid-Ask Spread | Direct cost of entering/exiting | Use limit orders to avoid paying the spread.41 |
| Latency | Speed of signal to execution | Use low-latency VPS and efficient APIs (\<100ms).6 |
| Market Depth | Stability of the price level | Avoid large orders relative to average volume.24 |
| Order Imbalance | Signals potential short-term move | Monitor the depth-of-book for "spoofing" or pressure.41 |

Algorithmic trading (AT) generally improves market liquidity by narrowing spreads, particularly in large-cap stocks.42 However, in times of stress, algorithms can "withdraw" from the market simultaneously, leading to a vacuum of liquidity where spreads widen dramatically.24 An agent must be programmed with "circuit breakers" to stop trading if volatility-adjusted spreads exceed a certain threshold, protecting the account from execution during "flash" events.44

## **Risk Management: The Mathematical Safety Harness**

The consensus across both academic research and professional trading is that risk management is the most critical determinant of long-term success.1 A strategy with a positive expectancy will still fail if the position sizing is not optimized. For an agent, risk management serves as the "safety harness" that keeps the system in the game during the inevitable periods of loss.4

### **Position Sizing and Capital Allocation Models**

The most common and effective risk rule for beginners is the "Fixed Percentage" method, risking no more than 1-2% of the total account balance on any single trade.44 This ensures that even a catastrophic loss on one stock does not significantly damage the portfolio’s growth potential.

The mathematical formula for position sizing is:

![][image2]  
By basing the position size on the distance to the stop-loss, the agent ensures that the dollar risk remains constant regardless of whether the stop-loss is tight (1%) or wide (5%).9

### **Advanced Risk Management Techniques**

For more sophisticated systems, other methods can be utilized to maximize the equity curve.

* **Volatility-Based Sizing (ATR):** Adjusting the position size based on the Average True Range (ATR). When volatility is high, position sizes are reduced to maintain consistent dollar risk.44  
* **The Kelly Criterion:** A formula that determines the optimal position size based on the historical win rate and the win/loss ratio:  
  ![][image3]  
  where ![][image4] is the probability of winning, ![][image5] is the probability of losing, and ![][image6] is the odds received on the wager.46 While powerful, the Kelly Criterion is aggressive and often used in "half-Kelly" or "fractional Kelly" formats to reduce the risk of ruin.47  
* **Value at Risk (VaR):** A statistical measure used to estimate the maximum potential loss over a given time period at a specific confidence level (e.g., 95%). VaR allows the agent to monitor its total "risk-at-risk" across all open positions, preventing over-correlation where many stocks in the same sector could all hit their stop-losses simultaneously.48

## **Stack Ranking the Success Parameters: A Prioritized Hierarchy**

To build a successful agent, one must understand that not all parameters are created equal. The following hierarchy ranks parameters based on their contribution to systematic trading success, derived from the synthesis of backtesting data, institutional factor research, and professional trader success formulas.1

| Priority Rank | Parameter Category | Role in Success | Contribution to Consistency |
| :---- | :---- | :---- | :---- |
| **1 (Critical)** | **Risk Management** | Capital Preservation | Prevents account ruin during losses.1 |
| **2 (Crucial)** | **Regime Detection** | Strategic Context | Ensures the strategy matches market state.10 |
| **3 (Primary)** | **Factor Synergy** | Alpha Generation | Combines Quality and Value for robust returns.21 |
| **4 (Strategic)** | **Psychological Rule-Adherence** | Operational Discipline | Prevents overtrading and emotional deviation.1 |
| **5 (Tactical)** | **Sentiment Analysis** | Leading Information | Gains an edge via alternative unstructured data.6 |
| **6 (Entry)** | **Technical Indicators** | Timing/Execution | Provides specific entry and exit price signals.12 |
| **7 (Operational)** | **Microstructure Efficiency** | Friction Reduction | Minimizes costs from slippage and spreads.14 |

At the base of the hierarchy is Risk Management; without it, even the most brilliant market analysis is unsustainable. Regime Detection and Factor Synergy represent the "core" of the strategy, ensuring that the agent is trading high-quality stocks in the correct environment. Technical indicators and sentiment analysis are the "execution" layer, providing the specific triggers for action.

## **Synthesis: What Makes Trading Successful?**

The pursuit of trading success is frequently mistaken for a search for the "perfect" indicator. However, successful trading is an emergent property of a system, not a characteristic of a single parameter. True success is defined by **expectancy**—the amount of money one can expect to make on each trade, on average, over a large sample size.2

Expectancy is calculated as:

![][image7]  
To achieve positive expectancy, a trader (or agent) must either have a high win rate with small gains (like RSI/Bollinger Band mean-reversion) or a low win rate with very large gains (like SMA trend-following).2

The ultimate "edge" for a Claude-powered agent is its capacity for **unemotional consistency**. By automating the analysis of fundamental quality, technical timing, and real-time sentiment, the agent can execute a strategy with the mechanical precision that human traders consistently lack.3 Success is therefore not found in predicting the future, but in identifying high-probability setups, managing the risk of being wrong, and adhering to a rigorous process through all market cycles.1 Through paper trading, the user can validate this process, ensuring that the expectancy is positive and the maximum drawdown is tolerable before deploying real capital.3

#### **Works cited**

1. The \#3 Golden Rules of Trading Success: The Foundation Every Trader Must Master \- FundingPips, accessed on April 11, 2026, [https://fundingpips.com/blog/the-3-golden-rules-of-trading-success-the-foundation-every-trader-must](https://fundingpips.com/blog/the-3-golden-rules-of-trading-success-the-foundation-every-trader-must)  
2. The Trading Success Formula | TradingwithRayner, accessed on April 11, 2026, [https://www.tradingwithrayner.com/trading-success-formula/](https://www.tradingwithrayner.com/trading-success-formula/)  
3. A Beginner's Guide to Build a Profitable Algo Trading Strategy \- Quantman, accessed on April 11, 2026, [https://www.quantman.trade/blog/a-beginners-guide-to-build-a-profitable-algo-trading-strategy/](https://www.quantman.trade/blog/a-beginners-guide-to-build-a-profitable-algo-trading-strategy/)  
4. Trading Psychology & Risk Management Explained: Discipline, Mindset & Capital Protection, accessed on April 11, 2026, [https://www.sahi.com/blogs/8-trading-psychology-and-risk-management](https://www.sahi.com/blogs/8-trading-psychology-and-risk-management)  
5. What really matters more in trading? technicals, fundamentals, or psychology? \- Reddit, accessed on April 11, 2026, [https://www.reddit.com/r/Daytrading/comments/1njqs9t/what\_really\_matters\_more\_in\_trading\_technicals/](https://www.reddit.com/r/Daytrading/comments/1njqs9t/what_really_matters_more_in_trading_technicals/)  
6. Leveraging AI Tools like Claude and ChatGPT in Algorithmic Trading, accessed on April 11, 2026, [https://www.quantvps.com/blog/algorithmic-trading-with-llm](https://www.quantvps.com/blog/algorithmic-trading-with-llm)  
7. AI Agent Development Example with Custom MCP Server: Part I \- Mobisoft Infotech, accessed on April 11, 2026, [https://mobisoftinfotech.com/resources/blog/ai-development/ai-agent-development-custom-mcp-server-code-review](https://mobisoftinfotech.com/resources/blog/ai-development/ai-agent-development-custom-mcp-server-code-review)  
8. Building a Multi-Agent AI Trading System: Technical Deep Dive into ..., accessed on April 11, 2026, [https://medium.com/@ishveen/building-a-multi-agent-ai-trading-system-technical-deep-dive-into-architecture-b5ba216e70f3](https://medium.com/@ishveen/building-a-multi-agent-ai-trading-system-technical-deep-dive-into-architecture-b5ba216e70f3)  
9. Risk Management and Trading Psychology \- Chart Champions, accessed on April 11, 2026, [https://chartchampions.com/risk-management-in-trading/](https://chartchampions.com/risk-management-in-trading/)  
10. How to establish a successful market regime filter? : r/algotrading \- Reddit, accessed on April 11, 2026, [https://www.reddit.com/r/algotrading/comments/1rvfy12/how\_to\_establish\_a\_successful\_market\_regime\_filter/](https://www.reddit.com/r/algotrading/comments/1rvfy12/how_to_establish_a_successful_market_regime_filter/)  
11. The Merits and Methods of Multi-Factor Investing \- S\&P Global, accessed on April 11, 2026, [https://www.spglobal.com/spdji/en/documents/research/research-the-merits-and-methods-of-multi-factor-investing.pdf](https://www.spglobal.com/spdji/en/documents/research/research-the-merits-and-methods-of-multi-factor-investing.pdf)  
12. Effectiveness of Technical Indicators in Stock Trading \- ResearchGate, accessed on April 11, 2026, [https://www.researchgate.net/publication/392414849\_Effectiveness\_of\_Technical\_Indicators\_in\_Stock\_Trading](https://www.researchgate.net/publication/392414849_Effectiveness_of_Technical_Indicators_in_Stock_Trading)  
13. Best Technical Indicators for Day Trading \[2026 Study\], accessed on April 11, 2026, [https://www.newtrading.io/best-technical-indicators/](https://www.newtrading.io/best-technical-indicators/)  
14. 5 Key Metrics to Monitor in Automated Trading Systems \- NURP, accessed on April 11, 2026, [https://nurp.com/algorithmic-trading-blog/5-key-metrics-automated-trading-systems/](https://nurp.com/algorithmic-trading-blog/5-key-metrics-automated-trading-systems/)  
15. How to Evaluate the Performance of Algorithmic Trading Strategies \- Tradetron, accessed on April 11, 2026, [https://tradetron.tech/blog/how-to-evaluate-the-performance-of-algorithmic-trading-strategies](https://tradetron.tech/blog/how-to-evaluate-the-performance-of-algorithmic-trading-strategies)  
16. View of Backtesting Brilliance: Leveraging Analytics for Comparing Buy & Hold Vs. Trading Strategies based on Technical Indicators \- Journal of Informatics Education and Research, accessed on April 11, 2026, [https://jier.org/index.php/journal/article/view/1785/1496](https://jier.org/index.php/journal/article/view/1785/1496)  
17. Analysing technical indicators combinations for profitable trading \- Virtus InterPress, accessed on April 11, 2026, [https://virtusinterpress.org/IMG/pdf/cbsrv5i1art15.pdf](https://virtusinterpress.org/IMG/pdf/cbsrv5i1art15.pdf)  
18. Relative Strength Index: How to Use it for Trading \- NewTrading.io, accessed on April 11, 2026, [https://www.newtrading.io/relative-strenght-index-rsi/](https://www.newtrading.io/relative-strenght-index-rsi/)  
19. Technical Analysis Indicators in Stock Market Using Machine Learning: A Comparative Analysis | Request PDF \- ResearchGate, accessed on April 11, 2026, [https://www.researchgate.net/publication/355893467\_Technical\_Analysis\_Indicators\_in\_Stock\_Market\_Using\_Machine\_Learning\_A\_Comparative\_Analysis](https://www.researchgate.net/publication/355893467_Technical_Analysis_Indicators_in_Stock_Market_Using_Machine_Learning_A_Comparative_Analysis)  
20. Fundamental Analysis of Stocks: Key Concepts, Metrics, and Techniques, accessed on April 11, 2026, [https://onlinedegrees.scu.edu/media/blog/fundamental-analysis-stocks](https://onlinedegrees.scu.edu/media/blog/fundamental-analysis-stocks)  
21. Fundamental Analysis: Combining the Search for Quality with the ..., accessed on April 11, 2026, [https://www.ivey.uwo.ca/media/3775546/mohanram.pdf](https://www.ivey.uwo.ca/media/3775546/mohanram.pdf)  
22. THE RELATIONSHIP BETWEEN FUNDAMENTAL ANALYSIS AND STOCK RETURNS USING PANEL DATA: EVIDENCE FROM KOMPAS 100 INDONESIA, accessed on April 11, 2026, [https://pdfs.semanticscholar.org/f374/1622dfccad2e1c46330467f4b16ca7f1687a.pdf](https://pdfs.semanticscholar.org/f374/1622dfccad2e1c46330467f4b16ca7f1687a.pdf)  
23. Analysis of Fundamental Factors on Stock Return \- HRMARS, accessed on April 11, 2026, [https://hrmars.com/papers\_submitted/6029/Analysis\_of\_Fundamental\_Factors\_on\_Stock\_Return.pdf](https://hrmars.com/papers_submitted/6029/Analysis_of_Fundamental_Factors_on_Stock_Return.pdf)  
24. How do algorithmic trading and high-frequency trading strategies affect liquidity in the markets? \- Financial Study Association Groningen, accessed on April 11, 2026, [https://fsgjournal.nl/article/2025-03-14-how-do-algorithmic-trading-and-high-frequency-trading-strategies-affect-liquidity-in-the-markets](https://fsgjournal.nl/article/2025-03-14-how-do-algorithmic-trading-and-high-frequency-trading-strategies-affect-liquidity-in-the-markets)  
25. Understanding Factor Investing \- AQR Funds, accessed on April 11, 2026, [https://funds.aqr.com/Insights/Strategies/Understanding-Factor-Investing](https://funds.aqr.com/Insights/Strategies/Understanding-Factor-Investing)  
26. Inside AQR Capital Management: How Multi-Factor Systematic Strategies Generate Returns, accessed on April 11, 2026, [https://navnoorbawa.substack.com/p/inside-aqr-capital-management-how](https://navnoorbawa.substack.com/p/inside-aqr-capital-management-how)  
27. MEASURING PORTFOLIO FACTOR EXPOSURES A Practical Guide \- AQR Capital Management, accessed on April 11, 2026, [https://www.aqr.com/-/media/AQR/Documents/Insights/Trade-Publications/Measuring-Portfolio-Factor-Exposures-A-Practical-Guide.pdf](https://www.aqr.com/-/media/AQR/Documents/Insights/Trade-Publications/Measuring-Portfolio-Factor-Exposures-A-Practical-Guide.pdf)  
28. A Better Way to Analyze Which Factors Drive Stock Returns | Chicago Booth Review, accessed on April 11, 2026, [https://www.chicagobooth.edu/review/better-way-analyze-which-factors-drive-stock-returns](https://www.chicagobooth.edu/review/better-way-analyze-which-factors-drive-stock-returns)  
29. Value of Alternative Data: The case of media sentiment \- LSEG, accessed on April 11, 2026, [https://www.lseg.com/content/dam/data-analytics/en\_us/documents/white-papers/re1623864-ia-probability-and-partners-alt-data-whitepaper.pdf](https://www.lseg.com/content/dam/data-analytics/en_us/documents/white-papers/re1623864-ia-probability-and-partners-alt-data-whitepaper.pdf)  
30. Alternative Data For Investing Market Research Report 2033 \- Dataintelo, accessed on April 11, 2026, [https://dataintelo.com/report/alternative-data-for-investing-market](https://dataintelo.com/report/alternative-data-for-investing-market)  
31. Rethinking Alternative Data in Institutional Investment \- CAIA, accessed on April 11, 2026, [https://caia.org/sites/default/files/014-031\_monk\_jfds.pdf](https://caia.org/sites/default/files/014-031_monk_jfds.pdf)  
32. Generating Alpha: A Hybrid AI-Driven Trading System Integrating Technical Analysis, Machine Learning and Financial Sentiment for Regime-Adaptive Equity StrategiesThis paper presents the full version of a work accepted for publication in the International Conference on Computing Systems and Intelligent Applications (ComSIA 2026), to appear in Springer Lecture Notes in Networks and Systems (LNNS \- arXiv, accessed on April 11, 2026, [https://arxiv.org/html/2601.19504v1](https://arxiv.org/html/2601.19504v1)  
33. Best AI & Alternative Data Analytics Platforms for Alpha Signal — BattleFin Events, accessed on April 11, 2026, [https://www.battlefin.com/the-ai-inflection-point/11-best-ai-alternative-data-analytics-platforms-for-alpha-signal](https://www.battlefin.com/the-ai-inflection-point/11-best-ai-alternative-data-analytics-platforms-for-alpha-signal)  
34. Alternative Data in Investment Management: Usage, Challenges and Valuation, accessed on April 11, 2026, [https://smallake.kr/wp-content/uploads/2021/01/SSRN-id3715828.pdf](https://smallake.kr/wp-content/uploads/2021/01/SSRN-id3715828.pdf)  
35. Market Regime Detection: Why Understanding ML Algorithms Matters | by Amina Kaltayeva, accessed on April 11, 2026, [https://medium.com/@amina.kaltayeva/market-regime-detection-why-understanding-ml-algorithms-matters-4eb7e8cac755](https://medium.com/@amina.kaltayeva/market-regime-detection-why-understanding-ml-algorithms-matters-4eb7e8cac755)  
36. Market Regime Detection using Hidden Markov Models in QSTrader | QuantStart, accessed on April 11, 2026, [https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/)  
37. GitHub \- tradermonty/claude-trading-skills: Claude Code skills for equity investors and traders — market analysis, technical charting, economic calendars, screeners, and trading strategy development., accessed on April 11, 2026, [https://github.com/tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills)  
38. What Is Anthropic's Managed Agents? How to Build and Deploy AI Agents Without Infrastructure | MindStudio, accessed on April 11, 2026, [https://www.mindstudio.ai/blog/what-is-anthropic-managed-agents-deploy-ai-without-infrastructure](https://www.mindstudio.ai/blog/what-is-anthropic-managed-agents-deploy-ai-without-infrastructure)  
39. modelcontextprotocol/servers: Model Context Protocol Servers \- GitHub, accessed on April 11, 2026, [https://github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)  
40. Impact Of Market Microstructure On Price Efficiency And Liquidity In Emerging Capital Markets, accessed on April 11, 2026, [http://ijeais.org/wp-content/uploads/2025/5/IJAAR250524.pdf](http://ijeais.org/wp-content/uploads/2025/5/IJAAR250524.pdf)  
41. Market Microstructure and Algorithmic Trading: A Practical Guide to Smarter Trade Execution \- NURP, accessed on April 11, 2026, [https://nurp.com/algorithmic-trading-blog/market-microstructure-and-algorithmic-trading/](https://nurp.com/algorithmic-trading-blog/market-microstructure-and-algorithmic-trading/)  
42. Does Algorithmic Trading Improve Liquidity? \- Meet the Berkeley-Haas Faculty, accessed on April 11, 2026, [https://faculty.haas.berkeley.edu/hender/Algo.pdf](https://faculty.haas.berkeley.edu/hender/Algo.pdf)  
43. Does Algorithmic Trading Improve Liquidity? \- Toulouse School of Economics, accessed on April 11, 2026, [https://www.tse-fr.eu/sites/default/files/medias/doc/sem/pwri/hendershottjonesmenkveld1.pdf](https://www.tse-fr.eu/sites/default/files/medias/doc/sem/pwri/hendershottjonesmenkveld1.pdf)  
44. Risk Management Strategies for Algo Trading \- LuxAlgo, accessed on April 11, 2026, [https://www.luxalgo.com/blog/risk-management-strategies-for-algo-trading/](https://www.luxalgo.com/blog/risk-management-strategies-for-algo-trading/)  
45. 7 Risk Management Strategies for Automated Algorithmic Trading \- NURP, accessed on April 11, 2026, [https://nurp.com/algorithmic-trading-blog/7-risk-management-strategies-for-algorithmic-trading/](https://nurp.com/algorithmic-trading-blog/7-risk-management-strategies-for-algorithmic-trading/)  
46. Risk Management in Algo Trading: Beyond Stop-Loss Orders — A 2026 Guide for Indian Traders \- AlgoBulls, accessed on April 11, 2026, [https://algobulls.com/blog/algo-trading/risk-management-in-algo-trading-india-2026](https://algobulls.com/blog/algo-trading/risk-management-in-algo-trading-india-2026)  
47. How to Manage Risk in Automated Trading \- TradersPost, accessed on April 11, 2026, [https://blog.traderspost.io/article/how-to-manage-risk-in-automated-trading](https://blog.traderspost.io/article/how-to-manage-risk-in-automated-trading)  
48. Achieve Trading Success: Master Your Mindset & Strategy, accessed on April 11, 2026, [https://tradewiththepros.com/achieve-trading-success/](https://tradewiththepros.com/achieve-trading-success/)  
49. Value at Risk (VaR) for Algorithmic Trading Risk Management \- Part I | QuantStart, accessed on April 11, 2026, [https://www.quantstart.com/articles/Value-at-Risk-VaR-for-Algorithmic-Trading-Risk-Management-Part-I/](https://www.quantstart.com/articles/Value-at-Risk-VaR-for-Algorithmic-Trading-Risk-Management-Part-I/)  
50. Risk Management & Trading Psychology \- AWS, accessed on April 11, 2026, [https://zerodha-common.s3.ap-south-1.amazonaws.com/Varsity/Modules/Module%209\_Risk%20Management%20%26%20Trading%20Psychology.pdf](https://zerodha-common.s3.ap-south-1.amazonaws.com/Varsity/Modules/Module%209_Risk%20Management%20%26%20Trading%20Psychology.pdf)  
51. Top 5 Metrics for Evaluating Trading Strategies \- LuxAlgo, accessed on April 11, 2026, [https://www.luxalgo.com/blog/top-5-metrics-for-evaluating-trading-strategies/](https://www.luxalgo.com/blog/top-5-metrics-for-evaluating-trading-strategies/)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAABACAYAAACnZCtBAAAFEElEQVR4Xu3dW6hmUxwA8DUat9yZQigTkUQKL6IRBiOD4YEaSZEMb6KQEA/kQXlze5GJhkieKIwnJsmU0ihTk5RyyaUwxGD92/t09rfOdy4z53y3s36/+vft9V/f6dt7nYf9b++1104JAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGCxbs3xX47XijwAACP2fI53c2xMCjYAgLGnYAMAGHMKNgBg7ByS47t2++Ic36emaKnVsAq2FTk+z3FJjs05duXYL8eaVPf4AwB9lMXBnj65msSxv14mByB+Iwq09Tl+LPpqHn8AoPBZmlkcRPu9IleTOP43ymQfJ+c4bwExm4faz205bup2pJn/EwCgYlEYlMVBtC8qcjWJ43+zTPZxbo5rFhDzKcf/+D45AKBiURi82mnf3uZqFsf/VpkcoHK8Yz5bmQMAKhaFQfd2XLR3d9o1ijF4u0wOyBOptzhb1bbP6eQAgMo9l+OXHNfm+Dc1xcKj3S9U4rocH6bmadkYg4j3c6zrfGcQ/k7Nb8Wt07Pb7TU93wAAeuwoE5VYmZpi4bTUFAwH9XYzQDHe8ZaFGP+a5w0CwAw7c/ya4+a2fVaOI1Oz/li4s/2szZZk7tQwHZGa8T6p7ACA2sX8rE9Tc6J8uuiLXCwiW6MHUnP8v6d6C9ZhijGOW9Ex5ncVfQBQvThBbipy8WRkXHHbnuPjHFt7u6twRWpW3F+b4/qij6UXc+Yuy3F5uw0AtI5Nc19FiwngAACMwFE5rsrxQpp+Iu/Cnm80DiwTQxCvJnql074jNa8sOqyTq0Fc4YslLvZv21fneGy6GwBY7mJF+ntS877GKNhie0PPN0ZnapL/T+32iakpMCdh8v+pqXlh+ULi/vZvZvNsagq0OO4/cpyf4762DQBUJE7+4/SOzAdT8xqiuJpWFibRPrPILbX4jfliGC5oPz9JM38z2ncXuaVWHvO4BABUKU6CG8vkGIhbgXGFqSv2NVa976c8sc8WR0/9wYSIff6y017d5m7o5LrK450tAIAJMbUobMwZGzfxsMNxRW4SCo2Y8/fUAmN9+zdziWO+sdN+sc2t6OQAgGXsybR0RdDLOf5aYMS8ufmU+3Vvn9xyF8tblMcc7XhdFgBQiXiLQVkQjIND08z9inb3ydEafJT6j8PhRQ4AWMbi5P94mRwD21Kzb3vaz5h4PwrH5DijTA5RHHu8U/Pndvub3u6JEEuSxFO+AMA+iiLggDI5BmK/viqTQ/ZtavZja9kxRPH7k1zs/JCaY3ik7AAA5hbrhMVJNJ4MLW+3jYvYr1vK5AjEflxaJodoXP8/eyOO4eAyCQDM7ZnUnERj8v/pRd+oRXH0Tmr2LxaIHbVRFUxxGzaWNInfjxeiT/IToaMaQwCgAqfk+LNMslduSwo2AGCAYpmSzTn+Sc3CtVF4TPKVrlGIhyRi3GIZkpjPFld1AQCWTBQaX3Ta8RDE7k6b+cUYdq+wxfb2ThsAYFHKW3kv9ckxtxivtZ32120OAGDRTkgzC4vf+uSYXb+nkMsrbgAA+yzeqFAWFtHeVeSY3dQ6dlNWtu24UgkAsGgPp95iY1PRZn4f5NjRaW9JxhAAWEKr0nRxEW+CiO11090swIY0PYbxtobYXj3dDQCweFempsiIuWtRwLH3pq5Uxu3ReKcoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzI/44GU8iyOBB2AAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAXCAYAAAAyet74AAAAp0lEQVR4XmNgGAXUBOpAPB2IBaB8YyDeAMSmcBVAwAjEl4DYCYj/A/FDIA6Cyv0G4gVQNsNqIGYCYl8GiEIlmAQQdEDFwKAGSp9AFoSCNVjEwAIgd6KLoSjkhgpIIomxQ8XykcQY2qGCyOAREH9DEwP7DqTwAwPE9I1A/ApFBRSAFM0CYmYgDgNiflRpCAAJghTKokugg0kMmO7DCmBBAMLmaHKDAQAA1WwkZEfq36MAAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAZCAYAAADjRwSLAAAAlElEQVR4XmNgGAU0A5eA+AUQ/wNiNyB+CMSGyAr+A3EdGh+E4eAjugAQPEMXA3GeIwtAxb7BOCFQgXS4NASAxGphnB1QAWSgAhVjhwlMgQoggyXoYtxoAsFQ/g8kMTBwhkqAsA+UbkBWgA7UGCCKONElkMF6Bkw3woE4EBczIKzNRJWGAEkgdgdiJyB2AeIAVGm6AQAwrybsyxK/hQAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAZCAYAAAAMhW+1AAAAhElEQVR4XmNgGDzgBBD/AuL/QGyGJgcH/QwQBTjBYwYCCkCSh9AFkQFIgSO6IAwkM0AUNALxcygbxbSHUEELJDEQPwCZcxQhBxe7gsxpR8jBxV6AGJJQDg+SJCNUbCKIkwblIINSqJgqiGMH5SADEP8RugAMdKDxwUARKgjC29HkRgIAAFc5JozAqrYVAAAAAElFTkSuQmCC>

[image7]: <data:image/png;base64,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>