# ggcorpframe demo — run with:
#   cd r-packages/ggcorpframe
#   /usr/local/bin/Rscript examples/gg_demo.R

library(ggplot2)
devtools::load_all(".")

# --- simple scatter plot ---
p <- ggplot(mtcars, aes(wt, mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  labs(x = "Weight (1000 lbs)", y = "Miles per Gallon", color = "Cylinders") +
  theme_minimal()

ggsave_corporate(p, "cars_corporate.png",
  title = "Weight vs Fuel Efficiency",
  subtitle = "Motor Trend Car Road Tests, 1974",
  footnotes = "N = 32 observations",
  sources = "Source: R datasets (mtcars)",
  width = 8, height = 5, dpi = 150
)

cat("Saved: cars_corporate.png\n")

# --- bar chart ---
avg_mpg <- aggregate(mpg ~ cyl, mtcars, mean)

p2 <- ggplot(avg_mpg, aes(factor(cyl), mpg, fill = factor(cyl))) +
  geom_col(show.legend = FALSE) +
  labs(x = "Cylinders", y = "Mean MPG") +
  theme_minimal()

ggsave_corporate(p2, "mpg_by_cyl.png",
  title = "Average Fuel Efficiency by Cylinder Count",
  sources = "Source: R datasets",
  width = 6, height = 4, dpi = 150
)

cat("Saved: mpg_by_cyl.png\n")
