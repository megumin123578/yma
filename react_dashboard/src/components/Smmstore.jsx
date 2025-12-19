import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { tokens } from "../theme";

const PACKAGES = [
  {
    id: "starter",
    name: "Starter Boost",
    desc: "Basic package for small channels.",
    price: "$9",
    items: ["1,000 views", "100 likes", "Delivery 24h"],
  },
  {
    id: "growth",
    name: "Growth Pack",
    desc: "Balanced package for steady growth.",
    price: "$29",
    items: ["5,000 views", "500 likes", "Delivery 48h"],
  },
  {
    id: "pro",
    name: "Pro Scale",
    desc: "High volume for campaigns.",
    price: "$79",
    items: ["20,000 views", "2,000 likes", "Priority support"],
  },
];

const Smmstore = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h5" color={colors.grey[100]} fontWeight="600">
          Simple Packages
        </Typography>
        <Typography variant="body2" color={colors.grey[300]}>
          Choose a package and place an order.
        </Typography>
      </Box>

      <Stack direction="row" spacing={2} flexWrap="wrap">
        {PACKAGES.map((pkg) => (
          <Paper
            key={pkg.id}
            elevation={0}
            sx={{
              p: 2,
              minWidth: 240,
              flex: "1 1 240px",
              borderRadius: 2,
              border: `1px solid ${theme.palette.divider}`,
              bgcolor:
                theme.palette.mode === "dark"
                  ? "rgba(17,17,17,0.6)"
                  : "rgba(255,255,255,0.9)",
            }}
          >
            <Stack spacing={1}>
              <Typography variant="h6" fontWeight="700">
                {pkg.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {pkg.desc}
              </Typography>
              <Typography variant="h4" fontWeight="800" color={colors.greenAccent[400]}>
                {pkg.price}
              </Typography>
              <Stack spacing={0.5}>
                {pkg.items.map((item) => (
                  <Typography key={item} variant="body2" color={colors.grey[200]}>
                    {item}
                  </Typography>
                ))}
              </Stack>
              <Button variant="contained" color="secondary">
                Order
              </Button>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
};

export default Smmstore;
